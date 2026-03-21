import asyncio
import base64
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
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
        get_history_filters,
        get_latest_video_for_session,
        get_session,
        get_session_products,
        get_sessions,
        get_sessions_detailed,
        init_db,
        save_session,
        save_session_products,
        save_video_metadata,
        update_session_video_path,
    )
    from .pdf_generator import generate_challan
    from .vision import VisionProcessor
else:
    from database import (
        get_dashboard_stats,
        get_history_filters,
        get_latest_video_for_session,
        get_session,
        get_session_products,
        get_sessions,
        get_sessions_detailed,
        init_db,
        save_session,
        save_session_products,
        save_video_metadata,
        update_session_video_path,
    )
    from pdf_generator import generate_challan
    from vision import VisionProcessor

logging.basicConfig(filename=str(LOGS_DIR / "nexustrace.log"), level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    VisionProcessor.cleanup_old_videos(max_age_days=30)
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


def _is_missing_video_source(video_source):
    if video_source is None:
        return True
    if isinstance(video_source, str):
        return not video_source.strip()
    return False


def _parse_products(payload):
    if payload is None:
        return []
    if isinstance(payload, str):
        parts = payload.split(",")
    elif isinstance(payload, (list, tuple, set)):
        parts = list(payload)
    else:
        parts = [payload]
    normalized = []
    seen = set()
    for value in parts:
        name = str(value or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(name)
    return normalized


def _session_tuple_to_dict(session):
    if not session:
        return None
    return {
        "id": session[0],
        "timestamp": session[1],
        "operator_id": session[2],
        "batch_id": session[3],
        "final_count": session[4],
        "video_path": session[5] if len(session) > 5 else None,
        "created_by": session[6] if len(session) > 6 else None,
        "started_at": session[7] if len(session) > 7 else None,
        "ended_at": session[8] if len(session) > 8 else None,
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    stats = get_dashboard_stats(is_admin=True)
    return {"stats": stats}


@app.get("/api/sessions/current")
async def current_session():
    metadata = vision.get_session_metadata()
    runtime = vision.get_runtime_metrics()
    return {"session": {**metadata, **runtime}}


@app.post("/api/sessions/products")
async def add_session_products(data: dict):
    if not vision.is_running():
        raise HTTPException(status_code=400, detail="No active session. Start a session first.")
    products = _parse_products(data.get("products") or data.get("product_types"))
    if not products:
        raise HTTPException(status_code=400, detail="products are required")
    updated = vision.add_products(products)
    return {"message": "Products updated", "products": updated}


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
    products = _parse_products(data.get("products"))
    product_type = str(data.get("product_type") or "").strip()
    if product_type:
        products = _parse_products(products + [product_type])

    if _is_missing_video_source(video_source):
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
            products=products,
        )
    except (FileNotFoundError, RuntimeError, ValueError, TypeError) as e:
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
        "products": vision.session_products,
        "started_at": vision.session_started_at,
    }


@app.post("/api/sessions/stop")
async def stop_session(data: dict):
    metadata = vision.get_session_metadata()
    if not vision.video_path:
        raise HTTPException(status_code=400, detail="No session is available to stop.")

    selected_products = _parse_products(data.get("challan_products"))

    count, video_path = vision.stop_session()
    operator_id = data.get("operator_id") or metadata.get("operator_id")
    batch_id = data.get("batch_id") or metadata.get("batch_id")
    started_at = metadata.get("started_at")
    ended_at = metadata.get("ended_at")

    session_id = save_session(
        operator_id,
        batch_id,
        count,
        video_path,
        created_by=None,
        started_at=started_at,
        ended_at=ended_at,
    )

    finalized_video_path, video_codec = vision.finalize_session_video(session_id)
    if finalized_video_path:
        update_session_video_path(session_id, finalized_video_path)
    save_video_metadata(session_id, finalized_video_path or video_path, codec=video_codec)

    product_counts = vision.final_product_counts or {}
    if not product_counts and metadata.get("products"):
        product_counts = {name: 0 for name in metadata.get("products", [])}
    save_session_products(session_id, product_counts, metadata.get("product_timestamps"))

    session = get_session(session_id, is_admin=True)
    session_dict = _session_tuple_to_dict(session)
    product_rows = get_session_products(session_id)
    try:
        challan_path = generate_challan(
            session_id=session_id,
            operator_id=session_dict["operator_id"],
            batch_id=session_dict["batch_id"],
            timestamp=session_dict["timestamp"],
            final_count=session_dict["final_count"],
            product_rows=product_rows,
            video_path=finalized_video_path or session_dict["video_path"],
            selected_products=selected_products or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Clear session identifiers so repeated stop calls don't duplicate records.
    vision.video_path = None
    vision.operator_id = None
    vision.batch_id = None
    vision.owner_user_id = None
    vision.session_products = []
    vision.session_products_lookup = set()

    return {
        "message": "Session stopped",
        "session_id": session_id,
        "final_count": count,
        "count_method": "final_check_median_recent_frames",
        "video_path": finalized_video_path or video_path,
        "challan_path": challan_path,
        "challan_file": Path(challan_path).name,
        "product_counts": product_counts,
    }


@app.get("/api/sessions/history")
async def get_history():
    sessions = get_sessions(is_admin=True)
    return {"sessions": sessions}


@app.get("/api/sessions/history/detailed")
async def get_history_detailed(
    search: str = Query(default="", description="Search by session id, operator, or batch"),
    operator_id: str = Query(default="", description="Filter by operator"),
    product_name: str = Query(default="", description="Filter by product"),
    date_from: str = Query(default="", description="YYYY-MM-DD inclusive start"),
    date_to: str = Query(default="", description="YYYY-MM-DD inclusive end"),
):
    sessions = get_sessions_detailed(
        is_admin=True,
        operator_id=operator_id or None,
        product_name=product_name or None,
        date_from=date_from or None,
        date_to=date_to or None,
        search=search or None,
    )
    return {"sessions": sessions}


@app.get("/api/sessions/history/filters")
async def get_history_filter_values():
    return get_history_filters()


@app.post("/api/challans/generate")
async def generate_challan_for_session(data: dict):
    session_id = data.get("session_id")
    if session_id is None:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        session_id = int(session_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="session_id must be an integer")
    selected_products = _parse_products(data.get("products"))
    if data.get("products") is not None and not selected_products:
        raise HTTPException(status_code=400, detail="products selection is empty")

    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_dict = _session_tuple_to_dict(session)
    products = get_session_products(session_id)
    video_row = get_latest_video_for_session(session_id)
    video_path = video_row["file_path"] if video_row else session_dict.get("video_path")

    try:
        challan_path = generate_challan(
            session_id=session_dict["id"],
            operator_id=session_dict["operator_id"],
            batch_id=session_dict["batch_id"],
            timestamp=session_dict["timestamp"],
            final_count=session_dict["final_count"],
            product_rows=products,
            video_path=video_path,
            selected_products=selected_products or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Challan generated",
        "challan_path": challan_path,
        "challan_file": Path(challan_path).name,
        "session_id": session_dict["id"],
        "products": selected_products or [row["product_name"] for row in products],
    }


@app.get("/api/challans/files/{file_name}")
async def get_challan_file(file_name: str):
    safe_name = Path(file_name).name
    challan_path = CHALLANS_DIR / safe_name
    if not challan_path.exists():
        raise HTTPException(status_code=404, detail="Challan file not found")
    return FileResponse(str(challan_path), media_type="application/pdf", filename=safe_name)


@app.get("/api/challans/{session_id}")
async def get_challan(session_id: int):
    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_dict = _session_tuple_to_dict(session)
    challan_path = CHALLANS_DIR / f"challan_{session_id}.pdf"
    if not challan_path.exists():
        product_rows = get_session_products(session_id)
        video_row = get_latest_video_for_session(session_id)
        try:
            generated = generate_challan(
                session_id=session_id,
                operator_id=session_dict["operator_id"],
                batch_id=session_dict["batch_id"],
                timestamp=session_dict["timestamp"],
                final_count=session_dict["final_count"],
                product_rows=product_rows,
                video_path=video_row["file_path"] if video_row else session_dict["video_path"],
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        challan_path = Path(generated)

    if not challan_path.exists():
        raise HTTPException(status_code=404, detail="Challan file not found")
    return FileResponse(str(challan_path), media_type="application/pdf", filename=challan_path.name)


@app.websocket("/ws/live-feed")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_sent_count = -1
    last_product_signature = ""
    try:
        while True:
            current_products = json.dumps(vision.latest_product_counts, sort_keys=True)
            should_send = (
                vision.latest_frame is not None
                and (
                    vision.is_running()
                    or vision.latest_count != last_sent_count
                    or current_products != last_product_signature
                )
            )

            if should_send:
                frame_b64 = base64.b64encode(vision.latest_frame).decode("utf-8")
                runtime = vision.get_runtime_metrics()
                await websocket.send_text(
                    json.dumps(
                        {
                            "frame": frame_b64,
                            "count": vision.latest_count,
                            "product_counts": runtime["product_counts"],
                            "fps": runtime["fps"],
                            "detection_confidence": runtime["detection_confidence"],
                            "duration_seconds": runtime["duration_seconds"],
                            "operator_id": runtime["operator_id"],
                            "batch_id": runtime["batch_id"],
                            "is_running": runtime["is_running"],
                        }
                    )
                )
                last_sent_count = vision.latest_count
                last_product_signature = current_products
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
