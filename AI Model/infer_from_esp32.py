import cv2, numpy as np, requests, time
from ultralytics import YOLO

ESP_IP = "http://172.20.10.6"          # <-- your current IP
SNAP   = f"{ESP_IP}/capture"           # fallback if MJPEG is flaky
MODEL  = YOLO("yolov8n.pt")            # person class = 0

CONF_TH = 0.5                          # tweak live
ROI_Y = 0.60                           # bottom 40% is "crossing zone"

def in_crossing_zone(box, h):
    _, y2 = box[1], box[3]             # xyxy
    return (y2 / h) >= ROI_Y

while True:
    t0 = time.time()
    jpg = requests.get(SNAP, timeout=2).content
    arr = np.frombuffer(jpg, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None: 
        continue

    h, w = frame.shape[:2]
    res = MODEL.predict(frame, classes=[0], conf=CONF_TH, verbose=False)[0]

    crossing = False
    for b in res.boxes.xyxy.cpu().numpy():
        x1,y1,x2,y2 = b[:4].astype(int)
        if in_crossing_zone((x1,y1,x2,y2), h): crossing = True
        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)

    # draw ROI line
    cv2.line(frame, (0,int(ROI_Y*h)), (w,int(ROI_Y*h)), (255,255,255), 2)
    txt = "PEDESTRIAN AHEAD" if crossing else "CLEAR"
    cv2.putText(frame, txt, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255) if crossing else (0,255,0), 2)

    cv2.imshow("PathGuard person detect", frame)
    if crossing:
        # TODO: trigger your ESP32 or backend (see step 4)
        pass

    if cv2.waitKey(1) == 27: break       # ESC to quit
    # Simple rate limit ~5 FPS
    dt = time.time() - t0
    if dt < 0.2: time.sleep(0.2 - dt)

cv2.destroyAllWindows()
