import re

with open('d:/Nexus_appmainp2/nexustrace/backend/vision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = content.replace('import time\nfrom collections import deque', 'import queue\nimport threading\nimport time\nfrom collections import deque')

# 2. init
old_init = '''        self.session_ended_at = None
        self.fps_value = 0.0
        self.latest_confidence = 0.0
        self.output_codec = "mp4v"'''
new_init = '''        self.session_ended_at = None
        self.fps_value = 0.0
        self.latest_confidence = 0.0
        self.output_codec = "mp4v"

        self.frame_queue = queue.Queue(maxsize=10)
        self.frame_skip_n = 2
        self.last_annotated_frame = None
        self.reader_thread = None
        self.worker_thread = None'''
content = content.replace(old_init, new_init)

# 3. start session
old_start = '''        self.cap = cv2.VideoCapture(parsed_source)
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
        self.out = cv2.VideoWriter(self.video_path, fourcc, fps, (width, height))'''

new_start = '''        self.cap = cv2.VideoCapture(parsed_source)
        if not self.cap.isOpened():
            self._release_resources()
            raise RuntimeError(f"Cannot open video source: {video_source}")

        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        self.last_annotated_frame = None

        fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 10.0)
        if fps <= 0 or fps > 120:
            fps = 10.0

        temp_video_name = f"session_pending_{int(time.time())}.mp4"
        self.video_path = str(VIDEOS_DIR / temp_video_name)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.output_codec = "mp4v"
        self.out = cv2.VideoWriter(self.video_path, fourcc, fps, (640, 480))'''
content = content.replace(old_start, new_start)

# 4. process frame
old_proc = '''        self._overlay_runtime(annotated_frame)

        ok, buffer = cv2.imencode(".jpg", annotated_frame)'''
new_proc = '''        self._overlay_runtime(annotated_frame)

        self.last_annotated_frame = annotated_frame

        ok, buffer = cv2.imencode(".jpg", annotated_frame)'''
content = content.replace(old_proc, new_proc)

# 5. run loop
old_loop = '''    def run_loop(self):
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
            self._release_resources()'''

new_loop = '''    def _frame_reader_loop(self):
        while self.running and self.cap is not None:
            ret, frame = self.cap.read()
            if not ret:
                logging.info("Video stream ended or frame read failed.")
                break
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(frame)

    def _detection_worker_loop(self):
        frame_index = 0
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            frame_index += 1
            if frame_index % self.frame_skip_n != 0:
                if getattr(self, "last_annotated_frame", None) is not None:
                    if self.out:
                        self.out.write(self.last_annotated_frame)
                continue
            frame_resized = cv2.resize(frame, (640, 480))
            self.process_frame(frame_resized)

    def run_loop(self):
        try:
            self.reader_thread = threading.Thread(target=self._frame_reader_loop, daemon=True)
            self.worker_thread = threading.Thread(target=self._detection_worker_loop, daemon=True)
            self.reader_thread.start()
            self.worker_thread.start()
            self.reader_thread.join()
            self.worker_thread.join()
        except Exception:
            logging.exception("Unexpected error in vision run loop")
        finally:
            self.running = False
            self._release_resources()'''
content = content.replace(old_loop, new_loop)

print("Old init found:", old_init in content, "after replace")
print("Old start found:", old_start in content, "after replace")

with open('d:/Nexus_appmainp2/nexustrace/backend/vision.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Replace done.")
