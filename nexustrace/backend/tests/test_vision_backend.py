import queue
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.vision import VisionProcessor  # noqa: E402


class _FailingCap:
    def read(self):
        return False, None


class VisionProcessorTests(unittest.TestCase):
    def test_resolve_yolov5_repo_path_requires_hubconf(self):
        processor = VisionProcessor(debug=False)
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError) as ctx:
                processor._resolve_yolov5_repo_path(temp_dir)
        self.assertIn("hubconf.py", str(ctx.exception))

    def test_load_roi_current_model_wraps_missing_dependency(self):
        processor = VisionProcessor(debug=False)
        processor.count_mode = "roi_current"

        missing_dep_error = ModuleNotFoundError("No module named 'pandas'")
        missing_dep_error.name = "pandas"
        with patch("backend.vision.torch.hub.load", side_effect=missing_dep_error):
            with self.assertRaises(RuntimeError) as ctx:
                processor._load_roi_current_model("model.pt", "repo")
        self.assertIn("Missing Python dependency", str(ctx.exception))
        self.assertIn("pandas", str(ctx.exception))

    def test_frame_reader_stops_session_when_stream_ends(self):
        processor = VisionProcessor(debug=False)
        processor.running = True
        processor.cap = _FailingCap()

        processor._frame_reader_loop()

        self.assertFalse(processor.running)

    def test_detection_worker_drains_queue_after_stop(self):
        processor = VisionProcessor(debug=False)
        processor.running = False
        processor.frame_skip_n = 1
        processor.frame_queue = queue.Queue(maxsize=2)
        processor.frame_queue.put(np.zeros((480, 640, 3), dtype=np.uint8))

        calls = {"count": 0}

        def _fake_process_frame(_frame):
            calls["count"] += 1

        processor.process_frame = _fake_process_frame
        processor._detection_worker_loop()

        self.assertEqual(calls["count"], 1)
        self.assertTrue(processor.frame_queue.empty())


if __name__ == "__main__":
    unittest.main()
