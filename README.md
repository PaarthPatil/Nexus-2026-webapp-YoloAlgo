# NexusTrace

NexusTrace is an application for object detection and counting using YOLOv5 models, with a web interface for real-time video processing and session management.

## Features

- Real-time object detection and counting from video sources
- Web-based dashboard for session control
- Live video feed via WebSocket
- Session history and challan generation
- Support for ROI-based counting

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
- **Count Mode**: Select counting method (e.g., "ROI Current Count")
- **YOLOv5 Repo Path**: Path to YOLOv5 directory
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