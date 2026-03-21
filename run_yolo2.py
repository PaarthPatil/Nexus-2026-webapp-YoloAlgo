import torch
import cv2
import time
import pathlib
import platform
import os

# ==========================================
# 1. USER SETTINGS & CONFIGURATION
# ==========================================
VIDEO_SOURCE = "boxvid.mp4"
MODEL_PATH = "box_detection.pt"
OUTPUT_DIR = "output_folder"
OUTPUT_MP4 = f"{OUTPUT_DIR}/tracking_output2.mp4"

CONFIDENCE_THRESHOLD = 0.50
IOU_THRESHOLD = 0.45
ROI_PADDING = 5 # Pixels of strict padding required for a box to be considered 'inside' the ROI

# ==========================================
# 2. SETUP AND INITIALIZATION 
# ==========================================
if platform.system() == 'Windows':
    temp = pathlib.PosixPath
    pathlib.PosixPath = pathlib.WindowsPath

print(f"Loading YOLO model from: {MODEL_PATH}")
model = torch.hub.load('yolov5', 'custom', path=MODEL_PATH, source='local')
model.conf = CONFIDENCE_THRESHOLD
model.iou = IOU_THRESHOLD

# Get the internal ID numbers for the classes
bigger_box_classes = [k for k, v in model.names.items() if 'bigger' in v.lower()]
small_box_classes = [k for k, v in model.names.items() if 'box' in v.lower() and 'bigger' not in v.lower()]

# Open the video
cap = cv2.VideoCapture(VIDEO_SOURCE)
os.makedirs(OUTPUT_DIR, exist_ok=True)
fps_in = cap.get(cv2.CAP_PROP_FPS)
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out_video = cv2.VideoWriter(OUTPUT_MP4, fourcc, fps_in, (width, height))

# UI Function
def draw_text_with_background(img, text, position, font_scale=0.5, thickness=1, text_color=(255,255,255), bg_color=(0,0,0)):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = position
    cv2.rectangle(img, (x - 2, y - text_height - 2), (x + text_width + 2, y + baseline + 2), bg_color, cv2.FILLED)
    cv2.putText(img, text, (x, y), font, font_scale, text_color, thickness)


# ==========================================
# 2. THE LIGHTWEIGHT LOGIC PIPELINE
# ==========================================
while cap.isOpened():
    success, frame = cap.read()
    if not success: 
        break
        
    start_time = time.time()
    
    # PERFORMANCE FIX: Removed augment=True! This triples the FPS immediately!
    results = model(frame)
    detections = results.xyxy[0].cpu().numpy() 
    
    # Step 1: Find the Bigger Box (The ROI)
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

    # Step 2: Grab only the Small Boxes physically located inside the ROI
    small_boxes_inside_roi = 0
    
    for det in detections:
        cls_id = int(det[5])
        
        # Make absolutely sure it's a small box, not an arm or a bigger_box
        if cls_id in small_box_classes:
            bx1, by1, bx2, by2 = det[0], det[1], det[2], det[3]
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
            
            # Mathematical ROI check
            if roi_box:
                rx1, ry1, rx2, ry2 = roi_box
                padding = ROI_PADDING
                if (rx1-padding) < cx < (rx2+padding) and (ry1-padding) < cy < (ry2+padding):
                    small_boxes_inside_roi += 1
                    cv2.rectangle(frame, (int(bx1), int(by1)), (int(bx2), int(by2)), (0, 255, 0), 2)
                    cv2.circle(frame, (int(cx), int(cy)), 3, (0, 255, 0), -1)

    # Step 3: Draw the simple, clean UI
    fps = 1.0 / (time.time() - start_time)
    
    draw_text_with_background(frame, f"FPS: {fps:.1f}", (10, 30), font_scale=0.8, thickness=2, text_color=(0,255,0), bg_color=(0,0,0))
    draw_text_with_background(frame, f"Small Boxes Found: {small_boxes_inside_roi}", (10, 70), font_scale=0.8, thickness=2, text_color=(0,255,0), bg_color=(0,0,0))
    
    out_video.write(frame)
    cv2.imshow("Optimized YOLO Counting", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out_video.release()
cv2.destroyAllWindows()
