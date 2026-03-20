## NexusTrace - Run & Usage Guide (No JWT)

### Current scope
- No login/auth required.
- Start/stop sessions, live feed, final-check counting, history, challan download.
- Supports ROI counting with your `D:\Nexus` model setup.

### Setup
```powershell
cd d:\Nexus_app\nexustrace
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
```

### Run backend
```powershell
cd d:\Nexus_app\nexustrace
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Run frontend
```powershell
cd d:\Nexus_app\nexustrace\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open: `http://127.0.0.1:5173`

### Use your `D:\Nexus` model (`run_yolo4` style)
Set these in the dashboard:
- Video source: `D:\Nexus\boxvid.mp4` (or webcam `0`)
- Model path: `box_detection.pt` (or full `D:\Nexus\box_detection.pt`)
- Count mode: `ROI Current Count (run_yolo4 style)`
- YOLOv5 repo path: `D:\Nexus\yolov5`
- Conf: `0.50`
- IOU: `0.65`
- ROI Padding: `5`
- ROI keyword: `bigger`
- Small box keyword: `box`

### Final count logic
- Final count is saved as a stable final-check value.
- Backend uses median of recent frame counts to reduce fake spike detections.

### Outputs
- DB: `backend\nexustrace.db`
- Videos: `backend\storage\videos\`
- Challans: `backend\storage\challans\`
- Logs: `backend\logs\nexustrace.log`
