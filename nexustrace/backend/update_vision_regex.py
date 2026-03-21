import re

with open('d:/Nexus_appmainp2/nexustrace/backend/vision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = re.sub(r'import time\s+from collections import deque', 'import queue\nimport threading\nimport time\nfrom collections import deque', content)

# 2. init
content = re.sub(r'(self\.output_codec = "mp4v"\s+)', r'\1\n        self.frame_queue = queue.Queue(maxsize=10)\n        self.frame_skip_n = 2\n        self.last_annotated_frame = None\n        self.reader_thread = None\n        self.worker_thread = None\n', content)

# 3. start session
start_pattern = r'(self\.cap = cv2\.VideoCapture\(parsed_source\)\s+if not self\.cap\.isOpened\(\):\s+self\._release_resources\(\)\s+raise RuntimeError\(f"Cannot open video source: \{video_source\}"\))(.*?)(self\.output_codec = "mp4v"\s+self\.out = cv2\.VideoWriter\(self\.video_path, fourcc, fps, \((?:width, height|640, 480)\)\))'

start_repl = r'''\1

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

content = re.sub(start_pattern, start_repl, content, flags=re.DOTALL)

# 4. process frame
proc_pattern = r'(self\._overlay_runtime\(annotated_frame\)\s+)(ok, buffer = cv2\.imencode\("\.jpg", annotated_frame\))'
proc_repl = r'\1self.last_annotated_frame = annotated_frame\n\n        \2'
content = re.sub(proc_pattern, proc_repl, content)

# 5. run loop
loop_pattern = r'    def run_loop\(self\):.*?self\._release_resources\(\)'
loop_repl = r'''    def _frame_reader_loop(self):
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
content = re.sub(loop_pattern, loop_repl, content, flags=re.DOTALL)

with open('d:/Nexus_appmainp2/nexustrace/backend/vision.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("done regex replacement")
