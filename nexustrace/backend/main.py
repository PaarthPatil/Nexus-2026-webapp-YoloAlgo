import asyncio
import base64
import json
import logging
import os
import socket
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

if __package__:
    from .config import CHALLANS_DIR, LOGS_DIR, ULTRALYTICS_SETTINGS_DIR, ensure_app_dirs
else:
    from config import CHALLANS_DIR, LOGS_DIR, ULTRALYTICS_SETTINGS_DIR, ensure_app_dirs

ensure_app_dirs()
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(ULTRALYTICS_SETTINGS_DIR))

if __package__:
    from .database import (
        count_users,
        create_user,
        get_dashboard_stats,
        get_history_filters,
        get_latest_video_for_session,
        get_session,
        get_session_products,
        get_sessions,
        get_sessions_detailed,
        get_user_by_id,
        get_user_by_username,
        get_video_by_id,
        get_videos_for_session,
        init_db,
        save_session,
        save_session_products,
        save_video_metadata,
        update_session_video_path,
    )
    from .auth import create_access_token, decode_access_token, hash_password, verify_password
    from .pdf_generator import generate_challan
    from .vision import VisionProcessor
else:
    from database import (
        count_users,
        create_user,
        get_dashboard_stats,
        get_history_filters,
        get_latest_video_for_session,
        get_session,
        get_session_products,
        get_sessions,
        get_sessions_detailed,
        get_user_by_id,
        get_user_by_username,
        get_video_by_id,
        get_videos_for_session,
        init_db,
        save_session,
        save_session_products,
        save_video_metadata,
        update_session_video_path,
    )
    from auth import create_access_token, decode_access_token, hash_password, verify_password
    from pdf_generator import generate_challan
    from vision import VisionProcessor

logging.basicConfig(filename=str(LOGS_DIR / "nexustrace.log"), level=logging.INFO)


def _bootstrap_admin_user():
    existing = get_user_by_username(ADMIN_USERNAME)
    if existing:
        return

    total_users = count_users()
    created = create_user(
        username=ADMIN_USERNAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        full_name=ADMIN_FULL_NAME,
        is_admin=True,
    )
    if created:
        logging.info("Bootstrapped default admin user '%s' (existing users before bootstrap: %s)", ADMIN_USERNAME, total_users)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _bootstrap_admin_user()
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


def _extract_bearer_token(header_value):
    raw = str(header_value or "").strip()
    if not raw:
        return None
    if raw.lower().startswith("bearer "):
        return raw.split(" ", 1)[1].strip()
    return None


def _current_user_from_request(request: Request):
    token = _extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return get_user_by_id(user_id)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path in PUBLIC_ROUTES:
        return await call_next(request)

    user = _current_user_from_request(request)
    if user is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Authentication required"},
        )

    request.state.user = user
    return await call_next(request)


vision = VisionProcessor()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_SUFFIXES = {".pt", ".pth", ".onnx", ".engine", ".tflite"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
PUBLIC_BASE_URL = os.getenv("NEXUSTRACE_PUBLIC_BASE_URL", "").strip().rstrip("/")
ADMIN_USERNAME = os.getenv("NEXUSTRACE_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("NEXUSTRACE_ADMIN_PASSWORD", "admin123")
ADMIN_FULL_NAME = os.getenv("NEXUSTRACE_ADMIN_FULL_NAME", "System Administrator")
PUBLIC_ROUTES = {
    "/api/health",
    "/api/auth/login",
}


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


def _discover_runner_scripts():
    scripts = []
    for script_path in sorted(PROJECT_ROOT.glob("run_yolo*.py")):
        mode = VisionProcessor.normalize_processing_mode(script_path.name)
        if mode not in VisionProcessor.SUPPORTED_PROCESSING_MODES:
            continue
        scripts.append(
            {
                "script_name": script_path.name,
                "mode": mode,
                "label": VisionProcessor.MODE_LABELS.get(mode, mode),
                "path": str(script_path.resolve()),
            }
        )
    return scripts


def _discover_model_files():
    seen = set()
    models = []
    for search_dir in [PROJECT_ROOT, PROJECT_ROOT / "nexustrace" / "backend"]:
        if not search_dir.exists():
            continue
        for path in sorted(search_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in MODEL_SUFFIXES:
                continue
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            models.append({"name": path.name, "path": resolved})
    return models


def _server_base_url(request: Request):
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    return str(request.base_url).rstrip("/")


def _local_network_base_url(request: Request):
    hostname = (request.url.hostname or "").lower()
    if hostname not in {"127.0.0.1", "localhost"}:
        return _server_base_url(request)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.connect(("8.8.8.8", 80))
        ip_address = sock.getsockname()[0]
        sock.close()
    except Exception:
        return _server_base_url(request)

    scheme = request.url.scheme or "http"
    port = request.url.port
    if port:
        return f"{scheme}://{ip_address}:{port}"
    return f"{scheme}://{ip_address}"


def _build_video_links(request: Request, session_id: int, video_id=None):
    base = _server_base_url(request)
    lan_base = _local_network_base_url(request)
    payload = {
        "session_video_url": f"{base}/api/video/{session_id}",
        "session_video_lan_url": f"{lan_base}/api/video/{session_id}",
    }
    if video_id is not None:
        payload["video_url"] = f"{base}/api/videos/{video_id}"
        payload["video_lan_url"] = f"{lan_base}/api/videos/{video_id}"
    return payload


def _resolve_video_file_path(file_path):
    raw = str(file_path or "").strip()
    if not raw:
        return None

    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (PROJECT_ROOT / candidate).resolve()

    if resolved.suffix.lower() not in VIDEO_SUFFIXES:
        raise HTTPException(status_code=404, detail="Video not available")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Video not available")
    return resolved


def _list_challan_files_for_session(session_id: int):
    files = []
    for challan_path in CHALLANS_DIR.glob(f"challan_{session_id}*.pdf"):
        created_iso = None
        try:
            created_iso = datetime.utcfromtimestamp(challan_path.stat().st_mtime).isoformat()
        except Exception:
            created_iso = None
        files.append(
            {
                "file_name": challan_path.name,
                "path": str(challan_path.resolve()),
                "created_at": created_iso,
            }
        )
    files.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return files


def _video_reference_for_pdf(request: Request, session_id: int, video_id, video_path):
    try:
        resolved = _resolve_video_file_path(video_path)
    except HTTPException:
        return None, None
    if resolved is None:
        return None, None
    links = _build_video_links(request, session_id, video_id)
    return links.get("video_url") or links["session_video_url"], resolved.name


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/auth/login")
async def login(data: dict):
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user.get("full_name"),
            "is_admin": bool(user.get("is_admin")),
        },
    }


@app.get("/api/auth/me")
async def me(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user.get("full_name"),
            "is_admin": bool(user.get("is_admin")),
        }
    }


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    stats = get_dashboard_stats(is_admin=True)
    return {"stats": stats}


@app.get("/api/sessions/current")
async def current_session():
    metadata = vision.get_session_metadata()
    runtime = vision.get_runtime_metrics()
    return {"session": {**metadata, **runtime}}


@app.get("/api/sessions/options")
async def session_options():
    return {
        "processing_modes": VisionProcessor.processing_mode_catalog(),
        "runner_scripts": _discover_runner_scripts(),
        "model_files": _discover_model_files(),
        "default_model_path": str(vision.default_model_path.resolve()),
    }


@app.get("/api/video/{session_id}")
async def get_session_video(session_id: int):
    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    video_row = get_latest_video_for_session(session_id)
    file_path = video_row["file_path"] if video_row else (session[5] if len(session) > 5 else None)
    resolved = _resolve_video_file_path(file_path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Video not available")
    return FileResponse(str(resolved), media_type="video/mp4", filename=resolved.name)


@app.get("/api/videos/{video_id}")
async def get_video_by_identifier(video_id: int):
    row = get_video_by_id(video_id)
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    resolved = _resolve_video_file_path(row.get("file_path"))
    if resolved is None:
        raise HTTPException(status_code=404, detail="Video not available")
    return FileResponse(str(resolved), media_type="video/mp4", filename=resolved.name)


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
    processing_mode = data.get("processing_mode", "yolo3")  # Default to yolo3
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
            processing_mode=processing_mode,
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
        "processing_mode": vision.processing_mode,
        "count_mode": vision.count_mode,
        "yolov5_repo_path": vision.yolov5_repo_path,
        "products": vision.session_products,
        "started_at": vision.session_started_at,
    }


@app.post("/api/sessions/stop")
async def stop_session(data: dict, request: Request):
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
    video_id = save_video_metadata(session_id, finalized_video_path or video_path, codec=video_codec)

    product_counts = vision.final_product_counts or {}
    if not product_counts and metadata.get("products"):
        product_counts = {name: 0 for name in metadata.get("products", [])}
    save_session_products(session_id, product_counts, metadata.get("product_timestamps"))

    session = get_session(session_id, is_admin=True)
    session_dict = _session_tuple_to_dict(session)
    product_rows = get_session_products(session_id)
    video_links = _build_video_links(request, session_id, video_id)
    resolved_video_path = finalized_video_path or session_dict["video_path"]
    video_reference_url, video_file_name = _video_reference_for_pdf(
        request, session_id, video_id, resolved_video_path
    )
    try:
        challan_path = generate_challan(
            session_id=session_id,
            operator_id=session_dict["operator_id"],
            batch_id=session_dict["batch_id"],
            timestamp=session_dict["timestamp"],
            final_count=session_dict["final_count"],
            product_rows=product_rows,
            video_path=resolved_video_path,
            video_file_name=video_file_name,
            video_reference_url=video_reference_url,
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
        "video_id": video_id,
        "video_url": video_links.get("video_url") or video_links["session_video_url"],
        "video_share_url": video_links.get("video_lan_url") or video_links["session_video_lan_url"],
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
    request: Request,
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
    for item in sessions:
        links = _build_video_links(request, item["id"], item.get("resolved_video_id"))
        try:
            _resolve_video_file_path(item.get("resolved_video_path"))
            item["video_url"] = links.get("video_url") or links["session_video_url"]
            item["video_share_url"] = links.get("video_lan_url") or links["session_video_lan_url"]
            item["video_available"] = True
        except HTTPException:
            item["video_url"] = None
            item["video_share_url"] = None
            item["video_available"] = False
    return {"sessions": sessions}


@app.get("/api/sessions/history/filters")
async def get_history_filter_values():
    return get_history_filters()


@app.get("/api/sessions/{session_id}/challans")
async def list_session_challans(session_id: int, request: Request):
    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    base = _server_base_url(request)
    challans = []
    for item in _list_challan_files_for_session(session_id):
        challans.append(
            {
                "file_name": item["file_name"],
                "url": f"{base}/api/challans/files/{quote(item['file_name'])}",
                "created_at": item["created_at"],
            }
        )
    return {"session_id": session_id, "challans": challans}


@app.get("/api/sessions/{session_id}/details")
async def get_session_details(session_id: int, request: Request):
    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_dict = _session_tuple_to_dict(session)
    products = get_session_products(session_id)
    videos = get_videos_for_session(session_id)
    latest_video = videos[0] if videos else None
    links = _build_video_links(request, session_id, latest_video.get("id") if latest_video else None)

    challans = []
    base = _server_base_url(request)
    for item in _list_challan_files_for_session(session_id):
        challans.append(
            {
                "file_name": item["file_name"],
                "url": f"{base}/api/challans/files/{quote(item['file_name'])}",
                "created_at": item["created_at"],
            }
        )

    for video in videos:
        video_url, video_name = _video_reference_for_pdf(
            request, session_id, video.get("id"), video.get("file_path")
        )
        video_links = _build_video_links(request, session_id, video.get("id"))
        video["video_url"] = video_url
        video["video_share_url"] = (
            video_links.get("video_lan_url") or video_links["session_video_lan_url"]
            if video_url
            else None
        )
        video["video_file_name"] = video_name

    latest_video_url, _latest_video_name = _video_reference_for_pdf(
        request,
        session_id,
        latest_video.get("id") if latest_video else None,
        latest_video.get("file_path") if latest_video else None,
    )

    return {
        "session": session_dict,
        "products": products,
        "videos": videos,
        "latest_video": latest_video,
        "video_url": latest_video_url,
        "video_share_url": (links.get("video_lan_url") or links["session_video_lan_url"]) if latest_video_url else None,
        "challans": challans,
    }


@app.post("/api/challans/generate")
async def generate_challan_for_session(data: dict, request: Request):
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
    video_reference_url, video_file_name = _video_reference_for_pdf(
        request, session_id, video_row.get("id") if video_row else None, video_path
    )

    try:
        challan_path = generate_challan(
            session_id=session_dict["id"],
            operator_id=session_dict["operator_id"],
            batch_id=session_dict["batch_id"],
            timestamp=session_dict["timestamp"],
            final_count=session_dict["final_count"],
            product_rows=products,
            video_path=video_path,
            video_file_name=video_file_name,
            video_reference_url=video_reference_url,
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
        "video_url": video_reference_url,
    }


@app.get("/api/challans/files/{file_name}")
async def get_challan_file(file_name: str):
    safe_name = Path(file_name).name
    challan_path = CHALLANS_DIR / safe_name
    if not challan_path.exists():
        raise HTTPException(status_code=404, detail="Challan file not found")
    return FileResponse(str(challan_path), media_type="application/pdf", filename=safe_name)


@app.get("/api/challans/{session_id}")
async def get_challan(session_id: int, request: Request):
    session = get_session(session_id, is_admin=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_dict = _session_tuple_to_dict(session)
    challan_path = CHALLANS_DIR / f"challan_{session_id}.pdf"
    if not challan_path.exists():
        product_rows = get_session_products(session_id)
        video_row = get_latest_video_for_session(session_id)
        video_path = video_row["file_path"] if video_row else session_dict["video_path"]
        video_links = _build_video_links(request, session_id, video_row.get("id") if video_row else None)
        video_reference_url, video_file_name = _video_reference_for_pdf(
            request, session_id, video_row.get("id") if video_row else None, video_path
        )
        try:
            generated = generate_challan(
                session_id=session_id,
                operator_id=session_dict["operator_id"],
                batch_id=session_dict["batch_id"],
                timestamp=session_dict["timestamp"],
                final_count=session_dict["final_count"],
                product_rows=product_rows,
                video_path=video_path,
                video_file_name=video_file_name,
                video_reference_url=video_reference_url,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        challan_path = Path(generated)

    if not challan_path.exists():
        raise HTTPException(status_code=404, detail="Challan file not found")
    return FileResponse(str(challan_path), media_type="application/pdf", filename=challan_path.name)


@app.websocket("/ws/live-feed")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload:
        await websocket.close(code=4401)
        return
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        await websocket.close(code=4401)
        return
    if not get_user_by_id(user_id):
        await websocket.close(code=4401)
        return

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
