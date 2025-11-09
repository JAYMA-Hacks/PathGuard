#!/usr/bin/env python3
# PathGuard / AI Model / people_counter.py
# - MJPEG from ESP32-CAM
# - YOLOv8 + ByteTrack -> count people per frame
# - Congestion policy: 0–1 low, 2–3 med, >=4 high
# - Draw boxes + numeric IDs on a live window
# - Post once per minute: {id, type:"congestion", lat, lng, val}
# - AWS endpoint/key from environment (.env)

import os, time, json, signal, csv
from collections import deque, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import numpy as np, requests, cv2

from ultralytics import YOLO
import supervision as sv
from dotenv import load_dotenv

load_dotenv(override=True)

# -------- Camera --------
CAM_BASE_URL = os.getenv("CAM_BASE_URL", "http://172.20.10.6")
STREAM_PATH  = os.getenv("STREAM_PATH", ":81/stream")  # change to "/stream" if you run the default port
CAPTURE_PATH = os.getenv("CAPTURE_PATH", "/capture")
STREAM_URL   = f"{CAM_BASE_URL}{STREAM_PATH}"
CAPTURE_URL  = f"{CAM_BASE_URL}{CAPTURE_PATH}"

# -------- Model / thresholds --------
MODEL_PATH   = os.getenv("MODEL_PATH", "yolov8n.pt")
CONF_THRESH  = float(os.getenv("CONF_THRESH", "0.35"))
IOU_THRESH   = float(os.getenv("IOU_THRESH", "0.45"))
IMG_SIZE     = int(os.getenv("IMG_SIZE", "640"))
PERSON_CLASS_ID = 0

# -------- Posting cadence / windows --------
ROLL_MIN_5   = int(os.getenv("ROLL_MIN_5", "5"))
ROLL_MIN_30  = int(os.getenv("ROLL_MIN_30", "30"))
POST_EVERY_S = int(os.getenv("POST_EVERY_S", "60"))
REENTRY_GRACE_S = int(os.getenv("REENTRY_GRACE_S", "45"))

# -------- Device / geo --------
DEVICE_ID     = os.getenv("DEVICE_ID", "esp32cam-01")
LAT           = float(os.getenv("LAT", "51.0189"))
LNG           = float(os.getenv("LON", "-114.1594")) * 1.0  # keep name 'lng' in payload

# -------- AWS --------
AWS_API     = os.getenv("AWS_API", "")
AWS_API_KEY = os.getenv("AWS_API_KEY", "")
TIMEOUT_S   = int(os.getenv("POST_TIMEOUT_S", "10"))
CSV_OUT     = os.getenv("CSV_OUT", "local_metrics.csv")

# -------- UI --------
WINDOW_TITLE = "PathGuard — People Counter (press q to quit)"

# -------- helpers --------
def utc_now():
    return datetime.now(timezone.utc)

def at_minute_boundary(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)

def post_to_aws(payload: dict) -> Tuple[bool, str]:
    if not AWS_API:
        return False, "No AWS_API set"
    headers = {"Content-Type": "application/json"}
    if AWS_API_KEY:
        headers["X-API-Key"] = AWS_API_KEY
    try:
        r = requests.post(AWS_API, headers=headers, data=json.dumps(payload), timeout=TIMEOUT_S)
        if r.ok:
            return True, f"{r.status_code}"
        else:
            return False, f"{r.status_code} {r.text[:200]}"
    except Exception as e:
        return False, str(e)

def append_csv(payload: dict):
    new_file = not os.path.exists(CSV_OUT)
    with open(CSV_OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(payload.keys()))
        if new_file:
            w.writeheader()
        w.writerow(payload)

# simple persistent counter for 'id'
COUNTER_PATH = ".counter"
def next_id():
    n = 0
    try:
        with open(COUNTER_PATH, "r") as f:
            n = int(f.read().strip())
    except:
        n = 0
    n += 1
    with open(COUNTER_PATH, "w") as f:
        f.write(str(n))
    return n

def congestion_from_count(n: int) -> str:
    # 0–1 low, 2–3 med, >=4 high
    if n <= 1: return "low"
    if n <= 3: return "med"
    return "high"

# -------- stream --------
def open_stream() -> Optional[cv2.VideoCapture]:
    cap = cv2.VideoCapture(STREAM_URL)
    if cap.isOpened():
        print(f"[i] Opened MJPEG stream: {STREAM_URL}")
        return cap
    print(f"[!] Could not open stream at {STREAM_URL}; will poll {CAPTURE_URL}")
    return None

def poll_capture_frame() -> Optional[np.ndarray]:
    try:
        resp = requests.get(CAPTURE_URL, timeout=5)
        if resp.ok:
            data = np.frombuffer(resp.content, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            return img
    except Exception:
        pass
    return None

def main():
    print("[i] Loading model:", MODEL_PATH)
    model = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack()

    # draw helpers
    box_annotator   = sv.BoxAnnotator(thickness=1)
    label_annotator = sv.LabelAnnotator()

    cap = open_stream()

    per_second_counts_5  = deque()
    per_second_counts_30 = deque()
    id_last_seen  = defaultdict(lambda: datetime.min.replace(tzinfo=timezone.utc))
    REENTRY_GRACE = timedelta(seconds=REENTRY_GRACE_S)

    last_summary_at = at_minute_boundary(utc_now()) - timedelta(seconds=1)

    running = True
    def handle_sigint(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, handle_sigint)

    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)

    while running:
        # fetch a frame
        if cap is not None:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
        else:
            frame = poll_capture_frame()
            if frame is None:
                time.sleep(0.1)
                continue

        # inference
        results = model.predict(source=frame, imgsz=IMG_SIZE, conf=CONF_THRESH, iou=IOU_THRESH, verbose=False)
        r = results[0]

        # keep only persons
        if r.boxes is None or len(r.boxes) == 0:
            det_xyxy = np.empty((0, 4), dtype=np.float32)
            det_conf = np.empty((0,), dtype=np.float32)
            det_cls  = np.empty((0,), dtype=np.int32)
        else:
            cls = r.boxes.cls.cpu().numpy().astype(int)
            keep = np.where(cls == PERSON_CLASS_ID)[0]
            det_xyxy = r.boxes.xyxy.cpu().numpy()[keep]
            det_conf = r.boxes.conf.cpu().numpy()[keep]
            det_cls  = cls[keep]

        dets = sv.Detections(xyxy=det_xyxy, confidence=det_conf, class_id=det_cls)
        tracks = tracker.update_with_detections(dets)

        # get track ids safely
        current_ids = []
        if hasattr(tracks, "tracker_id") and tracks.tracker_id is not None and tracks.tracker_id.size > 0:
            current_ids = [int(tid) for tid in tracks.tracker_id if tid is not None]
        current_count = len(set(current_ids))
        t = utc_now()

        # record last seen for re-entry debounce (here we just refresh)
        for tid in current_ids:
            id_last_seen[tid] = t

        # rolling windows
        cutoff5  = t - timedelta(minutes=ROLL_MIN_5)
        cutoff30 = t - timedelta(minutes=ROLL_MIN_30)

        per_second_counts_5.append((t, current_count))
        per_second_counts_30.append((t, current_count))
        while per_second_counts_5 and per_second_counts_5[0][0] < cutoff5:
            per_second_counts_5.popleft()
        while per_second_counts_30 and per_second_counts_30[0][0] < cutoff30:
            per_second_counts_30.popleft()

        # draw boxes + labels (ID numbers)
        annotated = frame.copy()
        if det_xyxy.shape[0] > 0:
            # build labels with ID numbers if we have them
            labels = []
            # Match up detections and track ids by index length
            # (ByteTrack returns tracks in same order as dets)
            for i in range(det_xyxy.shape[0]):
                tid_text = ""
                if hasattr(tracks, "tracker_id") and tracks.tracker_id is not None and tracks.tracker_id.size > i:
                    tid = tracks.tracker_id[i]
                    if tid is not None:
                        tid_text = f"ID {int(tid)}"
                labels.append(tid_text or "person")
            annotated = box_annotator.annotate(scene=annotated, detections=dets)
            annotated = label_annotator.annotate(scene=annotated, detections=dets, labels=labels)

        # show window
        cv2.imshow(WINDOW_TITLE, annotated)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # once per minute, post simplified payload
        t_minute = at_minute_boundary(t)
        if (t_minute - last_summary_at).total_seconds() >= POST_EVERY_S:
            # use instantaneous count for congestion (more responsive for demo)
            cong = congestion_from_count(current_count)

            payload = {
                "id": next_id(),
                "type": "congestion",
                "lat": float(LAT),
                "lng": float(LNG),
                "val": cong
            }

            ok, msg = post_to_aws(payload)
            if not ok:
                append_csv(payload)
            print(f"[summary] ok={ok} msg={msg} payload={payload}")
            last_summary_at = t_minute

    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    print("[i] Stopped.")

if __name__ == "__main__":
    main()
