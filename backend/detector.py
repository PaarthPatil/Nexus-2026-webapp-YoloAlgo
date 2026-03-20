from ultralytics import YOLO

model = YOLO("yolov8n.pt")

def get_count():
    # temporary test image (we'll switch to webcam next)
    results = model("https://ultralytics.com/images/bus.jpg")
    return len(results[0].boxes)
