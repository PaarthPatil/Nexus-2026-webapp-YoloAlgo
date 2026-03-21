import logging
import os
import pathlib
import shutil
import statistics
import subprocess
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import torch

if __package__:
    from .config import DEFAULT_MODEL_PATH, ULTRALYTICS_SETTINGS_DIR, VIDEOS_DIR, ensure_app_dirs
else:
    from config import DEFAULT_MODEL_PATH, ULTRALYTICS_SETTINGS_DIR, VIDEOS_DIR, ensure_app_dirs

ensure_app_dirs()
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(ULTRALYTICS_SETTINGS_DIR))

from ultralytics import YOLO


class VisionProcessor:
    def __init__(self, default_model_path=None, debug=True):
        self.default_model_path = Path(default_model_path) if default_model_path else DEFAULT_MODEL_PATH
        self.debug = debug

        self.model_path = None
        self.model = None
        self.count_mode = "track_unique"
        self.conf_threshold = 0.50
        self.iou_threshold = 0.65
        self.roi_padding = 5
        self.roi_label_keyword = "bigger"
        self.small_label_keyword = "box"
        self.yolov5_repo_path = None
        self.bigger_box_classes = []
        self.small_box_classes = []
        self.cumulative_unique_count = 0
        self.recent_counts = deque(maxlen=90)
        self.live_smoothing_window = 7
        self.final_window_size = 30

        self.seen_ids = set()
        self.product_recent_counts = {}
        self.product_first_seen = {}
        self.product_last_seen = {}
        self.session_products = []
        self.session_products_lookup = set()

        self.count = 0
        self.cap = None
        self.out = None
        self.running = False
        self.latest_frame = None
        self.latest_count = 0
        self.latest_product_counts = {}
        self.final_product_counts = {}
        self.video_path = None
        self.operator_id = None
        self.batch_id = None
        self.owner_user_id = None
        self.session_started_at = None
        self.session_ended_at = None
        self.fps_value = 0.0
        self.latest_confidence = 0.0
        self.output_codec = "mp4v"

    def is_running(self):
        return self.running

    def get_session_metadata(self):
        return {
            "operator_id": self.operator_id,
            "batch_id": self.batch_id,
            "owner_user_id": self.owner_user_id,
            "products": list(self.session_products),
            "started_at": self.session_started_at,
            "ended_at": self.session_ended_at,
            "product_timestamps": self.get_product_timestamps(),
        }

    def get_runtime_metrics(self):
        return {
            "is_running": self.running,
            "count": int(self.latest_count),
            "product_counts": dict(self.latest_product_counts),
            "fps": round(float(self.fps_value), 2),
            "detection_confidence": round(float(self.latest_confidence), 4),
            "started_at": self.session_started_at,
            "duration_seconds": self._get_duration_seconds(),
            "operator_id": self.operator_id,
            "batch_id": self.batch_id,
            "products": list(self.session_products),
            "video_path": self.video_path,
        }

    def get_product_timestamps(self):
        keys = set(self.product_first_seen.keys()) | set(self.product_last_seen.keys()) | set(self.session_products)
        payload = {}
        for product in sorted(keys):
            payload[product] = {
                "first_seen_at": self.product_first_seen.get(product),
                "last_seen_at": self.product_last_seen.get(product),
            }
        return payload

    def add_products(self, products):
        parsed = self._parse_products(products)
        if not parsed:
            return list(self.session_products)
        for name in parsed:
            if name.lower() in self.session_products_lookup:
                continue
            self.session_products.append(name)
            self.session_products_lookup.add(name.lower())
            self.product_recent_counts.setdefault(name, deque(maxlen=90))
            self.latest_product_counts.setdefault(name, 0)
        self._refresh_roi_product_filters()
        return list(self.session_products)

    def _get_duration_seconds(self):
        if not self.session_started_at:
            return 0
        try:
            started = datetime.fromisoformat(self.session_started_at)
        except ValueError:
            return 0
        ended = datetime.utcnow() if self.running else datetime.fromisoformat(self.session_ended_at or datetime.utcnow().isoformat())
        delta = ended - started
        return max(0, int(delta.total_seconds()))

    @staticmethod
    def _parse_products(products):
        if products is None:
            return []
        if isinstance(products, str):
            raw_items = products.split(",")
        elif isinstance(products, (list, tuple, set)):
            raw_items = list(products)
        else:
            raw_items = [products]

        seen = set()
        normalized = []
        for item in raw_items:
            name = str(item or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        return normalized

    def _should_track_product(self, product_name):
        if not self.session_products_lookup:
            return True
        return str(product_name or "").strip().lower() in self.session_products_lookup

    @staticmethod
    def _model_names_dict(names):
        if isinstance(names, dict):
            return {int(k): str(v) for k, v in names.items()}
        if isinstance(names, (list, tuple)):
            return {idx: str(v) for idx, v in enumerate(names)}
        return {}

    def _class_name_from_id(self, cls_id):
        names = self._model_names_dict(getattr(self.model, "names", {}))
        return names.get(int(cls_id), f"class_{int(cls_id)}")

    def _parse_video_source(self, video_source):
        if isinstance(video_source, str):
            source = video_source.strip()
            if source.isdigit():
                return int(source)
            return source
        return video_source

    def _resolve_model_path(self, model_path=None):
        candidate = str(model_path).strip() if model_path is not None else ""
        if not candidate:
            resolved = self.default_model_path
        else:
            raw_path = Path(candidate)
            if raw_path.exists():
                resolved = raw_path
            else:
                candidates = [
                    Path(__file__).resolve().parent / raw_path,
                    Path("D:/Nexus") / raw_path,
                    Path("D:/Nexus/box_detection") / raw_path,
                ]
                resolved = None
                for item in candidates:
                    if item.exists():
                        resolved = item
                        break
                if resolved is None:
                    if self.default_model_path.exists():
                        logging.warning("Model '%s' not found. Falling back to default model.", candidate)
                        resolved = self.default_model_path
                    else:
                        raise FileNotFoundError(
                            f"Model '{candidate}' not found and default model '{self.default_model_path}' is missing."
                        )
        return str(resolved.resolve())

    def _load_model(self, model_path):
        if self.model is not None and self.model_path == model_path:
            return
        self.model_path = model_path
        self.model = YOLO(self.model_path)

    def _resolve_yolov5_repo_path(self, repo_path=None):
        raw = str(repo_path).strip() if repo_path is not None else ""
        if raw and Path(raw).exists():
            return str(Path(raw).resolve())

        env_repo = os.getenv("NEXUSTRACE_YOLOV5_REPO", "").strip()
        if env_repo and Path(env_repo).exists():
            return str(Path(env_repo).resolve())

        for candidate in [Path("D:/Nexus/yolov5"), Path(__file__).resolve().parent / "yolov5"]:
            if candidate.exists():
                return str(candidate.resolve())

        raise FileNotFoundError(
            "YOLOv5 local repo path not found. Set `yolov5_repo_path` in request or "
            "`NEXUSTRACE_YOLOV5_REPO` environment variable."
        )

    def _load_roi_current_model(self, model_path, yolov5_repo_path):
        should_reload = (
            self.model is None
            or self.model_path != model_path
            or self.yolov5_repo_path != yolov5_repo_path
            or self.count_mode != "roi_current"
        )
        if not should_reload:
            return

        self.model_path = model_path
        self.yolov5_repo_path = yolov5_repo_path

        # Windows fix for weights saved with PosixPath inside older training environments.
        if os.name == "nt":
            pathlib.PosixPath = pathlib.WindowsPath

        self.model = torch.hub.load(yolov5_repo_path, "custom", path=model_path, source="local")

        self.model.conf = self.conf_threshold
        self.model.iou = self.iou_threshold
        self.model.agnostic = False
        self.model.max_det = 100

        names = self._model_names_dict(getattr(self.model, "names", {}))
        self.bigger_box_classes = [
            idx for idx, name in names.items() if self.roi_label_keyword in str(name).lower()
        ]
        self.small_box_classes = [
            idx
            for idx, name in names.items()
            if self.small_label_keyword in str(name).lower() and self.roi_label_keyword not in str(name).lower()
        ]

        self._refresh_roi_product_filters()

        if not self.bigger_box_classes:
            raise RuntimeError(
                f"No ROI class found. Expected class name containing '{self.roi_label_keyword}' in model labels."
            )
        if not self.small_box_classes:
            raise RuntimeError(
                f"No small-box class found. Expected class containing '{self.small_label_keyword}' excluding "
                f"'{self.roi_label_keyword}'."
            )

    def _refresh_roi_product_filters(self):
        if self.count_mode != "roi_current" or self.model is None:
            return
        names = self._model_names_dict(getattr(self.model, "names", {}))
        if not names:
            return
        if self.session_products_lookup:
            filtered = [
                idx
                for idx, name in names.items()
                if str(name).strip().lower() in self.session_products_lookup and idx not in self.bigger_box_classes
            ]
            if filtered:
                self.small_box_classes = filtered

    @staticmethod
    def _draw_text_with_background(
        frame,
        text,
        position,
        font_scale=0.6,
        thickness=1,
        text_color=(255, 255, 255),
        bg_color=(0, 0, 0),
    ):
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        x, y = position
        cv2.rectangle(
            frame,
            (x - 2, y - text_height - 2),
            (x + text_width + 2, y + baseline + 2),
            bg_color,
            cv2.FILLED,
        )
        cv2.putText(frame, text, (x, y), font, font_scale, text_color, thickness)

    def _reset_product_state(self):
        self.product_recent_counts = {}
        self.product_first_seen = {}
        self.product_last_seen = {}
        self.latest_product_counts = {}
        self.final_product_counts = {}
        for product in self.session_products:
            self.product_recent_counts[product] = deque(maxlen=90)
            self.latest_product_counts[product] = 0

    def start_session(
        self,
        video_source,
        operator_id,
        batch_id,
        model_path=None,
        owner_user_id=None,
        count_mode=None,
        yolov5_repo_path=None,
        conf_threshold=None,
        iou_threshold=None,
        roi_padding=None,
        roi_label_keyword=None,
        small_label_keyword=None,
        products=None,
    ):
        if self.running:
            raise RuntimeError("A session is already running.")

        ensure_app_dirs()

        self.count_mode = str(count_mode or "track_unique").strip().lower()
        if self.count_mode not in {"track_unique", "roi_current"}:
            raise RuntimeError("Unsupported count_mode. Allowed: track_unique, roi_current.")

        self.conf_threshold = float(conf_threshold) if conf_threshold is not None else 0.50
        self.iou_threshold = float(iou_threshold) if iou_threshold is not None else 0.65
        self.roi_padding = int(roi_padding) if roi_padding is not None else 5
        self.roi_label_keyword = str(roi_label_keyword or "bigger").strip().lower()
        self.small_label_keyword = str(small_label_keyword or "box").strip().lower()

        self.session_products = self._parse_products(products)
        self.session_products_lookup = {name.lower() for name in self.session_products}

        resolved_model_path = self._resolve_model_path(model_path)

        if self.count_mode == "roi_current":
            repo_path = self._resolve_yolov5_repo_path(yolov5_repo_path)
            self._load_roi_current_model(resolved_model_path, repo_path)
        else:
            self._load_model(resolved_model_path)

        self.seen_ids.clear()
        self.count = 0
        self.cumulative_unique_count = 0
        self.recent_counts.clear()
        self.latest_frame = None
        self.latest_count = 0
        self.fps_value = 0.0
        self.latest_confidence = 0.0
        self.operator_id = operator_id
        self.batch_id = batch_id
        self.owner_user_id = owner_user_id
        self.session_started_at = datetime.utcnow().isoformat()
        self.session_ended_at = None
        self._reset_product_state()

        parsed_source = self._parse_video_source(video_source)
        self.cap = cv2.VideoCapture(parsed_source)
        if not self.cap.isOpened():
            self._release_resources()
            raise RuntimeError(f"Cannot open video source: {video_source}")

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)
        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 10.0)
        if fps <= 0 or fps > 120:
            fps = 10.0

        temp_video_name = f"session_pending_{int(time.time())}.mp4"
        self.video_path = str(VIDEOS_DIR / temp_video_name)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.output_codec = "mp4v"
        self.out = cv2.VideoWriter(self.video_path, fourcc, fps, (width, height))
        if not self.out.isOpened():
            self._release_resources()
            raise RuntimeError("Failed to initialize output video writer.")

        self.running = True
        logging.info(
            "Session started: source=%s model=%s mode=%s products=%s",
            video_source,
            self.model_path,
            self.count_mode,
            ",".join(self.session_products) if self.session_products else "ALL",
        )

    def _release_resources(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.out:
            self.out.release()
            self.out = None

    def _compute_live_smoothed_product_counts(self):
        payload = {}
        keys = set(self.product_recent_counts.keys()) | set(self.session_products)
        for product in sorted(keys):
            values = list(self.product_recent_counts.get(product, []))
            if not values:
                payload[product] = 0
                continue
            window = values[-self.live_smoothing_window :]
            payload[product] = int(round(statistics.median(window)))
        return payload

    def _compute_final_product_counts(self):
        payload = {}
        keys = set(self.product_recent_counts.keys()) | set(self.session_products)
        for product in sorted(keys):
            values = list(self.product_recent_counts.get(product, []))
            if not values:
                payload[product] = 0
                continue
            window = values[-self.final_window_size :]
            payload[product] = int(round(statistics.median(window)))
        return payload

    def _record_product_frame_counts(self, product_counts):
        now = datetime.utcnow().isoformat()
        keys = set(product_counts.keys()) | set(self.session_products)
        for product in keys:
            count = max(0, int(product_counts.get(product, 0)))
            bucket = self.product_recent_counts.setdefault(product, deque(maxlen=90))
            bucket.append(count)
            if count > 0:
                if product not in self.product_first_seen:
                    self.product_first_seen[product] = now
                self.product_last_seen[product] = now
        self.latest_product_counts = self._compute_live_smoothed_product_counts()

    def stop_session(self):
        final_check_count = self._compute_final_check_count()
        self.final_product_counts = self._compute_final_product_counts()
        self.running = False
        self.session_ended_at = datetime.utcnow().isoformat()
        self._release_resources()
        logging.info("Session stopped")
        return final_check_count, self.video_path

    def _overlay_runtime(self, frame):
        self._draw_text_with_background(
            frame,
            f"Count: {int(self.latest_count)}",
            (10, 95),
            font_scale=0.65,
            thickness=2,
            text_color=(0, 255, 255),
            bg_color=(0, 0, 0),
        )
        self._draw_text_with_background(
            frame,
            f"FPS: {self.fps_value:.1f}",
            (10, 125),
            font_scale=0.65,
            thickness=2,
            text_color=(0, 255, 0),
            bg_color=(0, 0, 0),
        )
        self._draw_text_with_background(
            frame,
            f"Avg Conf: {self.latest_confidence:.2f}",
            (10, 155),
            font_scale=0.65,
            thickness=2,
            text_color=(255, 255, 0),
            bg_color=(0, 0, 0),
        )

        y = 185
        for product, value in list(self.latest_product_counts.items())[:5]:
            self._draw_text_with_background(
                frame,
                f"{product}: {value}",
                (10, y),
                font_scale=0.55,
                thickness=1,
                text_color=(255, 255, 255),
                bg_color=(35, 35, 35),
            )
            y += 24

    def process_frame(self, frame):
        if not self.running or self.model is None:
            return

        started = time.time()
        if self.count_mode == "roi_current":
            annotated_frame, frame_count, product_counts, confidences = self._process_frame_roi_mode(frame)
        else:
            annotated_frame, frame_count, product_counts, confidences = self._process_frame_track_mode(frame)

        self._record_frame_count(frame_count)
        self._record_product_frame_counts(product_counts)
        self.latest_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0
        elapsed = max(time.time() - started, 1e-6)
        self.fps_value = 1.0 / elapsed
        self._overlay_runtime(annotated_frame)

        ok, buffer = cv2.imencode(".jpg", annotated_frame)
        if ok:
            self.latest_frame = buffer.tobytes()
            self.latest_count = self._compute_live_smoothed_count()

        if self.out:
            self.out.write(annotated_frame)

    def _process_frame_track_mode(self, frame):
        results = self.model.track(frame, persist=True, verbose=self.debug)
        current_ids = set()
        without_id_count = 0
        per_product_counts = {}
        confidences = []

        boxes = results[0].boxes if results and results[0].boxes else []
        if boxes:
            for box in boxes:
                cls_id = int(box.cls.item()) if getattr(box, "cls", None) is not None else -1
                product_name = self._class_name_from_id(cls_id) if cls_id >= 0 else "unknown"

                if not self._should_track_product(product_name):
                    continue

                if getattr(box, "conf", None) is not None:
                    confidences.append(float(box.conf.item()))

                per_product_counts[product_name] = per_product_counts.get(product_name, 0) + 1

                if box.id is None:
                    without_id_count += 1
                else:
                    box_id = int(box.id.item())
                    current_ids.add(box_id)
                    seen_key = (product_name.lower(), box_id)
                    if seen_key not in self.seen_ids:
                        self.seen_ids.add(seen_key)
                        self.cumulative_unique_count += 1

        current_frame_count = len(current_ids) + without_id_count
        self.count = current_frame_count

        annotated = results[0].plot() if self.debug and results and results[0].boxes else frame
        return annotated, current_frame_count, per_product_counts, confidences

    def _process_frame_roi_mode(self, frame):
        results = self.model(frame)
        detections = results.xyxy[0].cpu().numpy() if hasattr(results, "xyxy") else []

        roi_box = None
        for det in detections:
            cls_id = int(det[5])
            if cls_id in self.bigger_box_classes:
                roi_box = (det[0], det[1], det[2], det[3])
                break

        if roi_box is not None:
            rx1, ry1, rx2, ry2 = map(int, roi_box)
            cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 0, 0), 2)
            self._draw_text_with_background(
                frame, "ROI Boundary", (rx1, max(20, ry1 - 5)), text_color=(255, 255, 255), bg_color=(255, 0, 0)
            )

        per_product_counts = {}
        confidences = []
        for det in detections:
            cls_id = int(det[5])
            confidence = float(det[4])
            confidences.append(confidence)
            if cls_id not in self.small_box_classes:
                continue

            label = self._class_name_from_id(cls_id)
            if not self._should_track_product(label):
                continue

            bx1, by1, bx2, by2 = det[0], det[1], det[2], det[3]
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2

            if roi_box is None:
                continue

            rx1, ry1, rx2, ry2 = roi_box
            pad = self.roi_padding
            if (rx1 - pad) < cx < (rx2 + pad) and (ry1 - pad) < cy < (ry2 + pad):
                per_product_counts[label] = per_product_counts.get(label, 0) + 1
                cv2.rectangle(frame, (int(bx1), int(by1)), (int(bx2), int(by2)), (0, 255, 0), 2)
                cv2.circle(frame, (int(cx), int(cy)), 3, (0, 255, 0), -1)
                self._draw_text_with_background(
                    frame,
                    f"{label} {confidence:.2f}",
                    (int(bx1), max(18, int(by1) - 6)),
                    font_scale=0.45,
                    thickness=1,
                    text_color=(255, 255, 255),
                    bg_color=(0, 120, 0),
                )

        frame_total = sum(per_product_counts.values())
        self.count = frame_total
        return frame, frame_total, per_product_counts, confidences

    def _record_frame_count(self, frame_count):
        value = max(0, int(frame_count))
        self.count = value
        self.recent_counts.append(value)

    def _compute_live_smoothed_count(self):
        if not self.recent_counts:
            return int(self.count)
        recent = list(self.recent_counts)[-self.live_smoothing_window :]
        return int(round(statistics.median(recent)))

    def _compute_final_check_count(self):
        if not self.recent_counts:
            return int(self.count)

        window = list(self.recent_counts)[-self.final_window_size :]
        if not window:
            return int(self.count)

        # Final-check logic: use median of recent frames to suppress occasional false detections.
        return int(round(statistics.median(window)))

    @staticmethod
    def _safe_timestamp_token(iso_value):
        try:
            return datetime.fromisoformat(iso_value).strftime("%Y%m%d_%H%M%S")
        except Exception:
            return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def _compress_video_h264(self, input_path: Path):
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return None

        compressed_path = input_path.with_name(f"{input_path.stem}_h264.mp4")
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            str(compressed_path),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            if compressed_path.exists() and compressed_path.stat().st_size > 0:
                return compressed_path
        except Exception:
            logging.exception("Video compression failed for %s", input_path)
        return None

    def finalize_session_video(self, session_id: int):
        if not self.video_path:
            return None, self.output_codec

        source = Path(self.video_path)
        if not source.exists():
            return str(source), self.output_codec

        timestamp_token = self._safe_timestamp_token(self.session_started_at)
        target = VIDEOS_DIR / f"session_{session_id}_{timestamp_token}.mp4"
        if source.resolve() != target.resolve():
            if target.exists():
                target.unlink()
            source.replace(target)

        codec = self.output_codec
        compressed = self._compress_video_h264(target)
        if compressed is not None:
            codec = "h264"
            try:
                if target.exists():
                    target.unlink()
                compressed.replace(target)
            except Exception:
                logging.exception("Failed to replace original video with compressed output")
                target = compressed

        self.video_path = str(target)
        self.cleanup_old_videos(max_age_days=30)
        return self.video_path, codec

    @staticmethod
    def cleanup_old_videos(max_age_days=30):
        ensure_app_dirs()
        threshold = datetime.utcnow() - timedelta(days=max_age_days)
        for path in VIDEOS_DIR.glob("session_*.mp4"):
            try:
                modified = datetime.utcfromtimestamp(path.stat().st_mtime)
                if modified < threshold:
                    path.unlink()
            except Exception:
                logging.exception("Failed to cleanup old video file: %s", path)

    def run_loop(self):
        try:
            while self.running and self.cap is not None:
                ret, frame = self.cap.read()
                if not ret:
                    logging.info("Video stream ended or frame read failed.")
                    break
                self.process_frame(frame)
                time.sleep(0.1)  # ~10 FPS for websocket updates
        except Exception:
            logging.exception("Unexpected error in vision run loop")
        finally:
            self.running = False
            self._release_resources()
