# NexusTrace

NexusTrace is an application for object detection and counting using YOLOv5 models, with a web interface for real-time video processing and session management.

## Features

- Real-time object detection and counting from video sources
- Web-based dashboard for session control
- Live video feed via WebSocket
- Session history and challan generation
- Support for ROI-based counting
- Multiple processing modes: YOLOv3, YOLOv4, YOLOv5 (Hysteresis), YOLO Raspberry Pi

## Project Structure

- `nexustrace/backend/` - FastAPI backend server
- `nexustrace/frontend/` - React frontend with Vite
- `yolov5/` - YOLOv5 repository for object detection
- `box_detection.pt` - Pre-trained model weights
- `run_yolo4.py` - YOLOv4 runner script

## Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Nexus_app
   ```

2. Set up the backend:
   ```bash
   cd nexustrace
   python -m venv .venv
   # On Windows:
   .\.venv\Scripts\Activate.ps1
   # On Unix:
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. Set up the frontend:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Usage

### Running the Backend

```bash
cd nexustrace
# Activate virtual environment
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Running the Frontend

```bash
cd nexustrace/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open your browser to `http://127.0.0.1:5173`

### Configuration

In the dashboard, configure:

- **Video Source**: Path to video file or webcam index (e.g., `0` for webcam)
- **Model Path**: Path to YOLO model weights (e.g., `box_detection.pt`)
- **Processing Mode**: Choose from YOLOv3, YOLOv4, YOLOv5 (Hysteresis), or YOLO Raspberry Pi
- **Count Mode**: Select counting method (e.g., "ROI Current Count")
- **YOLOv5 Repo Path** (optional): Path to YOLOv5 directory (auto-detected if left empty)
- **Confidence Threshold**: Detection confidence (default: 0.50)
- **IOU Threshold**: Intersection over Union threshold (default: 0.65)
- **ROI Padding**: Padding for region of interest
- **ROI Label Keyword**: Keyword for ROI labels
- **Small Label Keyword**: Keyword for small object labels

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/dashboard/stats` - Dashboard statistics
- `POST /api/sessions/start` - Start a new session
- `POST /api/sessions/stop` - Stop current session
- `GET /api/sessions/history` - Get session history
- `GET /api/challans/{session_id}` - Download challan PDF
- `WebSocket /ws/live-feed` - Live video feed

## Development

### Backend

The backend uses FastAPI with the following key components:

- `vision.py` - Video processing and object detection
- `database.py` - SQLite database operations
- `pdf_generator.py` - Challan PDF generation

### Frontend

The frontend is built with React and Vite, using Tailwind CSS for styling.

## License

[Add license information here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Quick Start (copy/paste)

### Windows (PowerShell)

```powershell
# 1) Clone repo and install dependencies
cd d:\Nexus_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r nexustrace\backend\requirements.txt
cd nexustrace\frontend
npm install
cd ..\..

# 2) Start backend (in its own terminal)
cd nexustrace
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3) Start frontend (in another terminal)
cd d:\Nexus_app\nexustrace\frontend
npm run dev -- --host 127.0.0.1 --port 5173

# 4) Open browser
start http://127.0.0.1:5173
```

### Linux / macOS (bash/zsh)

```bash
# 1) Clone repo and install dependencies
cd /path/to/Nexus_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r nexustrace/backend/requirements.txt
cd nexustrace/frontend
npm install
cd ../..

# 2) Start backend (in its own terminal)
cd nexustrace
source ../.venv/bin/activate
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3) Start frontend (in another terminal)
cd /path/to/Nexus_app/nexustrace/frontend
npm run dev -- --host 127.0.0.1 --port 5173

# 4) Open browser
xdg-open http://127.0.0.1:5173  # Linux
# open http://127.0.0.1:5173    # macOS
```

### Cross-platform YOLOv5 path notes

- In UI, `YOLOv5 Repo Path` is optional.
- If empty, backend auto-detects `yolov5` in common project locations.
- You can also set an explicit path via env var:
  - `NEXUSTRACE_YOLOV5_REPO=/abs/path/to/yolov5` (Linux/macOS)
  - `$env:NEXUSTRACE_YOLOV5_REPO='D:\path\to\yolov5'` (Windows PowerShell)

### Default Login

- Username: `admin`
- Password: `admin123`
- Override via env vars:
  - `NEXUSTRACE_ADMIN_USERNAME`
  - `NEXUSTRACE_ADMIN_PASSWORD`
