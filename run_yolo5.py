import torch
import cv2
import time
import pathlib
import platform
import os
import numpy as np
from collections import OrderedDict, deque


# 0. HYSTERESIS CENTROID TRACKER
class HysteresisTracker:
    def __init__(self, maxDisappeared=20, maxDistance=60):
        # Centroid History: We remember where a box is and its trajectory
        self.nextObjectID = 1
        self.objects = OrderedDict()
        self.disappeared = OrderedDict()
        self.maxDisappeared = maxDisappeared
        self.maxDistance = maxDistance

    def register(self, centroid):
        self.objects[self.nextObjectID] = centroid
        self.disappeared[self.nextObjectID] = 0
        self.nextObjectID += 1

    def deregister(self, objectID):
        del self.objects[objectID]
        del self.disappeared[objectID]

    def update(self, rects, confidences, init_threshold=0.60):
        if len(rects) == 0:
            for objectID in list(self.disappeared.keys()):
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.maxDisappeared:
                    self.deregister(objectID)
            return self.objects

        inputCentroids = np.zeros((len(rects), 2), dtype="int")
        for (i, (startX, startY, endX, endY)) in enumerate(rects):
            cX = int((startX + endX) / 2.0)
            cY = int((startY + endY) / 2.0)
            inputCentroids[i] = (cX, cY)

        if len(self.objects) == 0:
            for i in range(0, len(inputCentroids)):
                # HYSTERESIS LOGIC: Only register a brand new object if confidence is > 0.60
                if confidences[i] >= init_threshold:
                    self.register(inputCentroids[i])
        else:
            objectIDs = list(self.objects.keys())
            objectCentroids = list(self.objects.values())
            
            D = np.linalg.norm(np.array(objectCentroids)[:, np.newaxis] - inputCentroids, axis=2)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            usedRows, usedCols = set(), set()
            for (row, col) in zip(rows, cols):
                if row in usedRows or col in usedCols: continue
                if D[row, col] > self.maxDistance: continue

                objectID = objectIDs[row]
                # HYSTERESIS LOGIC: Box is actively tracked even if confidence is weak (down to 0.40 system global bounds)
                self.objects[objectID] = inputCentroids[col]
                self.disappeared[objectID] = 0
                usedRows.add(row), usedCols.add(col)

            unusedRows = set(range(0, D.shape[0])).difference(usedRows)
            unusedCols = set(range(0, D.shape[1])).difference(usedCols)

            for row in unusedRows:
                objectID = objectIDs[row]
                self.disappeared[objectID] += 1
                if self.disappeared[objectID] > self.maxDisappeared:
                    self.deregister(objectID)

            for col in unusedCols:
                # HYSTERESIS LOGIC: Must be high confidence (0.60+) to initialize tracking
                if confidences[col] >= init_threshold:
                    self.register(inputCentroids[col])

        return self.objects


# 1. USER SETTINGS & CONFIGURATION
VIDEO_SOURCE = "boxvid.mp4"
MODEL_PATH = "box_detection.pt"
OUTPUT_DIR = "output_folder"
OUTPUT_MP4 = f"{OUTPUT_DIR}/tracking_output5.mp4"

# LOWER BOUND of Hysteresis! Any box worse than 40% is instantly shredded over the entire system.
CONFIDENCE_LOWER_BOUND = 0.40 
IOU_THRESHOLD = 0.45
ROI_PADDING = 5 

if platform.system() == 'Windows':
    temp = pathlib.PosixPath
    pathlib.PosixPath = pathlib.WindowsPath

model = torch.hub.load('yolov5', 'custom', path=MODEL_PATH, source='local')
model.conf = CONFIDENCE_LOWER_BOUND 
model.iou = IOU_THRESHOLD 
model.agnostic = False 
model.max_det = 100 

bigger_box_classes = [k for k, v in model.names.items() if 'bigger' in v.lower()]
small_box_classes = [k for k, v in model.names.items() if 'box' in v.lower() and 'bigger' not in v.lower()]

cap = cv2.VideoCapture(VIDEO_SOURCE)
os.makedirs(OUTPUT_DIR, exist_ok=True)
fps_in = cap.get(cv2.CAP_PROP_FPS)
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out_video = cv2.VideoWriter(OUTPUT_MP4, fourcc, fps_in, (width, height))

def draw_text_with_background(img, text, position, font_scale=0.5, thickness=1, text_color=(255,255,255), bg_color=(0,0,0)):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = position
    cv2.rectangle(img, (x - 2, y - text_height - 2), (x + text_width + 2, y + baseline + 2), bg_color, cv2.FILLED)
    cv2.putText(img, text, (x, y), font, font_scale, text_color, thickness)


# ==========================================
# 4. EXECUTION LOOP
# ==========================================
# The Tracker + Temporal Smoothing Buffer setup
tracker = HysteresisTracker(maxDisappeared=20, maxDistance=60)
count_history = deque(maxlen=15) # Takes the absolute average of the last 15 frames (0.5 seconds of math)

while cap.isOpened():
    success, frame = cap.read()
    if not success: 
        break
        
    start_time = time.time()
    
    results = model(frame)
    detections = results.xyxy[0].cpu().numpy() 
    
    roi_box = None
    for det in detections:
        cls_id = int(det[5])
        if cls_id in bigger_box_classes:
            roi_box = (det[0], det[1], det[2], det[3])
            break 

    if roi_box:
        rx1, ry1, rx2, ry2 = map(int, roi_box)
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 0, 0), 2)
        draw_text_with_background(frame, "ROI Boundary", (rx1, ry1 - 5), text_color=(255,255,255), bg_color=(255,0,0))

    rects_to_track = []
    confs_to_track = []
    
    for det in detections:
        cls_id = int(det[5])
        
        if cls_id in small_box_classes:
            bx1, by1, bx2, by2 = det[0], det[1], det[2], det[3]
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
            conf = det[4]
            
            if roi_box:
                rx1, ry1, rx2, ry2 = roi_box
                padding = ROI_PADDING
                if (rx1-padding) < cx < (rx2+padding) and (ry1-padding) < cy < (ry2+padding):
                    rects_to_track.append([bx1, by1, bx2, by2])
                    confs_to_track.append(conf) # Capture the confidence for Hysteresis!
                    cv2.rectangle(frame, (int(bx1), int(by1)), (int(bx2), int(by2)), (0, 255, 0), 2)

    # 1. Execute Centroid Tracker & Hysteresis
    # init_threshold = 0.60: Must be 60%+ certain to be considered a new box!
    objects = tracker.update(rects_to_track, confs_to_track, init_threshold=0.60)
    current_raw_count = len(objects)
    
    # Draw tracker markers
    for (objectID, centroid) in objects.items():
        cv2.circle(frame, (centroid[0], centroid[1]), 3, (0, 255, 255), -1)
        draw_text_with_background(frame, f"#{objectID}", (centroid[0]-10, centroid[1]-10), font_scale=0.4, bg_color=(0,100,100))

    # 2. Execute Temporal Smoothing (The Persistence Buffer)
    count_history.append(current_raw_count)
    history_list = list(count_history)
    # The most frequently occurring number in the last 15 frames is crowned the Official Count!
    official_smoothed_count = max(set(history_list), key=history_list.count) if history_list else 0

    fps = 1.0 / (time.time() - start_time)
    
    draw_text_with_background(frame, f"FPS: {fps:.1f}", (10, 30), font_scale=0.8, thickness=2, text_color=(0,255,0), bg_color=(0,0,0))
    # We display the Mathematically Smoothed persistence tracker value
    draw_text_with_background(frame, f"Official Validated Count: {official_smoothed_count}", (10, 70), font_scale=0.8, thickness=2, text_color=(0,255,255), bg_color=(0,0,0))
    
    out_video.write(frame)
    cv2.imshow("Tri-Optimized Defense Pipeline", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out_video.release()
cv2.destroyAllWindows()
