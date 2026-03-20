import logging
import os
import pathlib
import statistics
import time
from collections import deque
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
        self.count = 0
        self.cap = None
        self.out = None
        self.running = False
        self.latest_frame = None
        self.latest_count = 0
        self.video_path = None
        self.operator_id = None
        self.batch_id = None
        self.owner_user_id = None

    def is_running(self):
        return self.running

    def get_session_metadata(self):
        return {
            "operator_id": self.operator_id,
            "batch_id": self.batch_id,
            "owner_user_id": self.owner_user_id,
        }

    def _parse_video_source(self, video_source):
        if isinstance(video_source, str):
            source = video_source.strip()
            if source.isdigit():
                return int(source)
            return source
        return video_source

    def _resolve_model_path(self, model_path=None):
        candidate = (model_path or "").strip()
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
        raw = (repo_path or "").strip()
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

        names = self.model.names
        self.bigger_box_classes = [
            idx for idx, name in names.items() if self.roi_label_keyword in str(name).lower()
        ]
        self.small_box_classes = [
            idx
            for idx, name in names.items()
            if self.small_label_keyword in str(name).lower() and self.roi_label_keyword not in str(name).lower()
        ]

        if not self.bigger_box_classes:
            raise RuntimeError(
                f"No ROI class found. Expected class name containing '{self.roi_label_keyword}' in model labels."
            )
        if not self.small_box_classes:
            raise RuntimeError(
                f"No small-box class found. Expected class containing '{self.small_label_keyword}' excluding "
                f"'{self.roi_label_keyword}'."
            )

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
    ):
        if self.running:
            raise RuntimeError("A session is already running.")

        ensure_app_dirs()

        self.count_mode = (count_mode or "track_unique").strip().lower()
        if self.count_mode not in {"track_unique", "roi_current"}:
            raise RuntimeError("Unsupported count_mode. Allowed: track_unique, roi_current.")

        self.conf_threshold = float(conf_threshold) if conf_threshold is not None else 0.50
        self.iou_threshold = float(iou_threshold) if iou_threshold is not None else 0.65
        self.roi_padding = int(roi_padding) if roi_padding is not None else 5
        self.roi_label_keyword = (roi_label_keyword or "bigger").strip().lower()
        self.small_label_keyword = (small_label_keyword or "box").strip().lower()

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
        self.operator_id = operator_id
        self.batch_id = batch_id
        self.owner_user_id = owner_user_id

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

        safe_operator = str(operator_id or "unknown_operator").strip().replace(" ", "_")
        safe_batch = str(batch_id or "unknown_batch").strip().replace(" ", "_")
        self.video_path = str(VIDEOS_DIR / f"session_{safe_operator}_{safe_batch}_{int(time.time())}.mp4")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.out = cv2.VideoWriter(self.video_path, fourcc, fps, (width, height))
        if not self.out.isOpened():
            self._release_resources()
            raise RuntimeError("Failed to initialize output video writer.")

        self.running = True
        logging.info("Session started: source=%s model=%s mode=%s", video_source, self.model_path, self.count_mode)

    def _release_resources(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.out:
            self.out.release()
            self.out = None

    def stop_session(self):
        final_check_count = self._compute_final_check_count()
        self.running = False
        self._release_resources()
        logging.info("Session stopped")
        return final_check_count, self.video_path

    def process_frame(self, frame):
        if not self.running or self.model is None:
            return

        if self.count_mode == "roi_current":
            annotated_frame, frame_count = self._process_frame_roi_mode(frame)
        else:
            annotated_frame, frame_count = self._process_frame_track_mode(frame)

        self._record_frame_count(frame_count)

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

        if results and results[0].boxes:
            for box in results[0].boxes:
                if box.id is None:
                    without_id_count += 1
                else:
                    box_id = int(box.id.item())
                    current_ids.add(box_id)
                    if box_id not in self.seen_ids:
                        self.seen_ids.add(box_id)
                        self.cumulative_unique_count += 1

        current_frame_count = len(current_ids) + without_id_count
        self.count = current_frame_count

        annotated = results[0].plot() if self.debug and results and results[0].boxes else frame
        return annotated, current_frame_count

    def _process_frame_roi_mode(self, frame):
        start = time.time()
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

        small_boxes_inside_roi = 0
        for det in detections:
            cls_id = int(det[5])
            if cls_id not in self.small_box_classes:
                continue

            bx1, by1, bx2, by2 = det[0], det[1], det[2], det[3]
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2

            if roi_box is None:
                continue

            rx1, ry1, rx2, ry2 = roi_box
            pad = self.roi_padding
            if (rx1 - pad) < cx < (rx2 + pad) and (ry1 - pad) < cy < (ry2 + pad):
                small_boxes_inside_roi += 1
                cv2.rectangle(frame, (int(bx1), int(by1)), (int(bx2), int(by2)), (0, 255, 0), 2)
                cv2.circle(frame, (int(cx), int(cy)), 3, (0, 255, 0), -1)

        self.count = small_boxes_inside_roi

        elapsed = max(time.time() - start, 1e-6)
        fps = 1.0 / elapsed
        self._draw_text_with_background(
            frame,
            f"FPS: {fps:.1f}",
            (10, 30),
            font_scale=0.7,
            thickness=2,
            text_color=(0, 255, 0),
        )
        self._draw_text_with_background(
            frame,
            f"Current Deliveries In ROI Box: {small_boxes_inside_roi}",
            (10, 65),
            font_scale=0.7,
            thickness=2,
            text_color=(0, 255, 0),
        )

        return frame, small_boxes_inside_roi

    def _record_frame_count(self, frame_count):
        value = max(0, int(frame_count))
        self.count = value
        self.recent_counts.append(value)

    def _compute_live_smoothed_count(self):
        if not self.recent_counts:
            return int(self.count)
        recent = list(self.recent_counts)[-self.live_smoothing_window:]
        return int(round(statistics.median(recent)))

    def _compute_final_check_count(self):
        if not self.recent_counts:
            return int(self.count)

        window = list(self.recent_counts)[-self.final_window_size:]
        if not window:
            return int(self.count)

        # Final-check logic: use median of recent frames to suppress occasional false detections.
        return int(round(statistics.median(window)))

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
