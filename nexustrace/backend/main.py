import logging
import os
import threading
import json
import base64
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

if __package__:
    from .config import CHALLANS_DIR, LOGS_DIR, ULTRALYTICS_SETTINGS_DIR, ensure_app_dirs
else:
    from config import CHALLANS_DIR, LOGS_DIR, ULTRALYTICS_SETTINGS_DIR, ensure_app_dirs

ensure_app_dirs()
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(ULTRALYTICS_SETTINGS_DIR))

if __package__:
    from .database import (
        get_dashboard_stats,
        get_session,
        get_sessions,
        init_db,
        save_session,
    )
    from .pdf_generator import generate_challan
    from .vision import VisionProcessor
else:
    from database import (
        get_dashboard_stats,
        get_session,
        get_sessions,
        init_db,
        save_session,
    )
    from pdf_generator import generate_challan
    from vision import VisionProcessor

logging.basicConfig(filename=str(LOGS_DIR / "nexustrace.log"), level=logging.INFO)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

vision = VisionProcessor()


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    stats = get_dashboard_stats(is_admin=True)
    return {"stats": stats}


@app.post("/api/sessions/start")
async def start_session(data: dict):
    operator_id = data.get("operator_id")
    batch_id = data.get("batch_id")
    video_source = data.get("video_source")
    model_path = data.get("model_path")
    count_mode = data.get("count_mode")
    yolov5_repo_path = data.get("yolov5_repo_path")
    conf_threshold = data.get("conf_threshold")
    iou_threshold = data.get("iou_threshold")
    roi_padding = data.get("roi_padding")
    roi_label_keyword = data.get("roi_label_keyword")
    small_label_keyword = data.get("small_label_keyword")

    if not video_source:
        raise HTTPException(status_code=400, detail="video_source is required")
    if vision.is_running():
        raise HTTPException(status_code=409, detail="A session is already running.")

    try:
        vision.start_session(
            video_source,
            operator_id,
            batch_id,
            model_path=model_path,
            count_mode=count_mode,
            yolov5_repo_path=yolov5_repo_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            roi_padding=roi_padding,
            roi_label_keyword=roi_label_keyword,
            small_label_keyword=small_label_keyword,
        )
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Failed to start session")
        raise HTTPException(status_code=500, detail=str(e))

    threading.Thread(target=vision.run_loop, daemon=True).start()
    return {
        "message": "Session started",
        "model_path": vision.model_path,
        "count_mode": vision.count_mode,
        "yolov5_repo_path": vision.yolov5_repo_path,
    }

@app.post("/api/sessions/stop")
async def stop_session(data: dict):
    metadata = vision.get_session_metadata()
    if not vision.video_path:
        raise HTTPException(status_code=400, detail="No session is available to stop.")

    count, video_path = vision.stop_session()
    operator_id = data.get("operator_id") or metadata.get("operator_id")
    batch_id = data.get("batch_id") or metadata.get("batch_id")

    session_id = save_session(
        operator_id,
        batch_id,
        count,
        video_path,
        created_by=None,
    )
    session = get_session(session_id, is_admin=True)
    challan_path = generate_challan(session_id, session[2], session[3], session[1], session[4])

    # Clear session identifiers so repeated stop calls don't duplicate records.
    vision.video_path = None
    vision.operator_id = None
    vision.batch_id = None
    vision.owner_user_id = None

    return {
        "message": "Session stopped",
        "session_id": session_id,
        "final_count": count,
        "count_method": "final_check_median_recent_frames",
        "video_path": video_path,
        "challan_path": challan_path,
    }

@app.get("/api/sessions/history")
async def get_history():
    sessions = get_sessions(is_admin=True)
    return {"sessions": sessions}

@app.get("/api/challans/{session_id}")
async def get_challan(session_id: int):
    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    challan_path = CHALLANS_DIR / f"challan_{session_id}.pdf"
    if not challan_path.exists():
        raise HTTPException(status_code=404, detail="Challan file not found")
    return FileResponse(str(challan_path), media_type="application/pdf", filename=f"challan_{session_id}.pdf")

@app.websocket("/ws/live-feed")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_sent_count = -1
    try:
        while True:
            if vision.latest_frame is not None and (vision.is_running() or vision.latest_count != last_sent_count):
                frame_b64 = base64.b64encode(vision.latest_frame).decode("utf-8")
                await websocket.send_text(json.dumps({"frame": frame_b64, "count": vision.latest_count}))
                last_sent_count = vision.latest_count
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logging.info("WebSocket client disconnected")
    except Exception:
        logging.exception("WebSocket error")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
