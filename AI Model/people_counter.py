#!/usr/bin/env python3
# PathGuard / AI Model / people_counter.py
import os, time, json, signal, csv
from collections import deque, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import numpy as np, requests, cv2
from ultralytics import YOLO
import supervision as sv
from dotenv import load_dotenv

load_dotenv(override=True)

CAM_BASE_URL   = os.getenv("CAM_BASE_URL", "http://172.20.10.6")
STREAM_PATH    = os.getenv("STREAM_PATH", ":81/stream")
CAPTURE_PATH   = os.getenv("CAPTURE_PATH", "/capture")
STREAM_URL     = f"{CAM_BASE_URL}{STREAM_PATH}"
CAPTURE_URL    = f"{CAM_BASE_URL}{CAPTURE_PATH}"

MODEL_PATH     = os.getenv("MODEL_PATH", "yolov8n.pt")
CONF_THRESH    = float(os.getenv("CONF_THRESH", "0.35"))
IOU_THRESH     = float(os.getenv("IOU_THRESH", "0.45"))
IMG_SIZE       = int(os.getenv("IMG_SIZE", "640"))

ROLL_MIN_5     = int(os.getenv("ROLL_MIN_5", "5"))
ROLL_MIN_30    = int(os.getenv("ROLL_MIN_30", "30"))
POST_EVERY_S   = int(os.getenv("POST_EVERY_S", "60"))
REENTRY_GRACE_S= int(os.getenv("REENTRY_GRACE_S", "45"))

DEVICE_ID      = os.getenv("DEVICE_ID", "esp32cam-01")
AREA_ID        = os.getenv("AREA_ID", "heritage_park")
LOCATION_NAME  = os.getenv("LOCATION_NAME", "Calgary – Test Corner")
LAT            = float(os.getenv("LAT", "51.0447"))
LON            = float(os.getenv("LON", "-114.0719"))

AWS_API        = os.getenv("AWS_API", "")
AWS_API_KEY    = os.getenv("AWS_API_KEY", "")
TIMEOUT_S      = int(os.getenv("POST_TIMEOUT_S", "10"))

CSV_OUT        = os.getenv("CSV_OUT", "local_metrics.csv")
OBFUSCATE      = int(os.getenv("OBFUSCATE", "0"))

PERSON_CLASS_ID = 0

def utc_now():
    return datetime.now(timezone.utc)

def at_minute_boundary(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)

def obfuscate_value(v: float) -> float:
    if not OBFUSCATE:
        return round(v, 2)
    bucketed = round(v * 2) / 2.0
    import random
    jitter = (random.random() - 0.5) * 0.05
    return max(0.0, round(bucketed + jitter, 2))

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

    cap = open_stream()

    per_second_counts_5  = deque()   # (ts, count)
    per_second_counts_30 = deque()
    id_first_seen = {}
    id_last_seen  = defaultdict(lambda: datetime.min.replace(tzinfo=timezone.utc))
    REENTRY_GRACE = timedelta(seconds=REENTRY_GRACE_S)

    last_summary_at = at_minute_boundary(utc_now()) - timedelta(seconds=1)

    running = True
    def handle_sigint(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, handle_sigint)

    while running:
        if cap is not None:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.1)
                continue
        else:
            frame = poll_capture_frame()
            if frame is None:
                time.sleep(0.25)
                continue

        results = model.predict(source=frame, imgsz=IMG_SIZE, conf=CONF_THRESH, iou=IOU_THRESH, verbose=False)
        r = results[0]

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

        detections = sv.Detections(xyxy=det_xyxy, confidence=det_conf, class_id=det_cls)
        tracks = tracker.update_with_detections(detections)

        current_ids = set([tid for tid in tracks.tracker_id if tid is not None])
        current_count = len(current_ids)
        t = utc_now()

        for tid in current_ids:
            if tid in id_first_seen:
                id_last_seen[tid] = t
            else:
                if (t - id_last_seen[tid]) <= REENTRY_GRACE:
                    id_last_seen[tid] = t
                else:
                    id_first_seen[tid] = t
                    id_last_seen[tid]  = t

        cutoff5  = t - timedelta(minutes=ROLL_MIN_5)
        cutoff30 = t - timedelta(minutes=ROLL_MIN_30)

        to_del = [tid for tid, last in id_last_seen.items() if last < cutoff30]
        for tid in to_del:
            id_first_seen.pop(tid, None)
            id_last_seen.pop(tid, None)

        per_second_counts_5.append((t, current_count))
        per_second_counts_30.append((t, current_count))
        while per_second_counts_5 and per_second_counts_5[0][0] < cutoff5:
            per_second_counts_5.popleft()
        while per_second_counts_30 and per_second_counts_30[0][0] < cutoff30:
            per_second_counts_30.popleft()

        t_minute = at_minute_boundary(t)
        if (t_minute - last_summary_at).total_seconds() >= 60:
            avg5  = (sum(c for _, c in per_second_counts_5)  / max(1, len(per_second_counts_5)))  if per_second_counts_5  else 0.0
            avg30 = (sum(c for _, c in per_second_counts_30) / max(1, len(per_second_counts_30))) if per_second_counts_30 else 0.0
            uniq30 = sum(1 for _tid in id_first_seen.keys() if id_last_seen[_tid] >= cutoff30)

            payload = {
                "item_type": "crowd_avg_5m",
                "area_id": AREA_ID,
                "source": "analytics_service",
                "ts": t_minute.isoformat().replace("+00:00","Z"),
                "device_id": DEVICE_ID,
                "avg_people_5m":  obfuscate_value(avg5),
                "avg_people_30min": obfuscate_value(avg30),
                "unique_people_30min": int(uniq30),
                "lat": LAT,
                "lon": LON,
                "location_name": LOCATION_NAME
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
