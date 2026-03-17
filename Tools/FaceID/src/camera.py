"""
FaceID Camera Module
====================

Captures frames from the MacBook camera using OpenCV.
Handles camera lifecycle, frame grabbing, and cleanup.
"""

import cv2
import numpy as np
import logging
import time as _time
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Rate-limit camera error logging to once per 60 seconds
_last_capture_error_log: float = 0.0
_CAPTURE_ERROR_LOG_INTERVAL: float = 60.0


@dataclass
class Frame:
    """A captured camera frame with metadata."""
    image: np.ndarray       # BGR frame from OpenCV
    timestamp: float        # time.time() when captured
    width: int
    height: int


class Camera:
    """
    MacBook camera interface.
    
    Usage:
        cam = Camera()
        cam.open()
        frame = cam.capture()
        cam.close()
    
    Or as context manager:
        with Camera() as cam:
            frame = cam.capture()
    """
    
    def __init__(self, device_id: int = 0, width: int = 640, height: int = 480):
        self.device_id = device_id
        self.width = width
        self.height = height
        self._cap: Optional[cv2.VideoCapture] = None
    
    def open(self) -> bool:
        """Open the camera. Returns True if successful."""
        import time

        self._cap = cv2.VideoCapture(self.device_id)
        if not self._cap.isOpened():
            logger.error(f"Failed to open camera {self.device_id}")
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        # Warm up — macOS camera needs time to initialize hardware
        # Wait up to 3 seconds for the first valid frame
        logger.info("Waiting for camera to initialize...")
        for attempt in range(30):
            ret, frame = self._cap.read()
            if ret and frame is not None and frame.size > 0:
                logger.info(f"Camera ready after {attempt + 1} attempts")
                break
            time.sleep(0.1)
        else:
            logger.warning("Camera warmup: never got a valid frame, proceeding anyway")

        logger.info(f"Camera {self.device_id} opened ({self.width}x{self.height})")
        return True
    
    def capture(self) -> Optional[Frame]:
        """Capture a single frame. Returns None if capture fails."""
        import time

        if self._cap is None or not self._cap.isOpened():
            logger.error("Camera not open")
            return None

        # Retry a few times — macOS can drop individual frames
        for _ in range(3):
            ret, image = self._cap.read()
            if ret and image is not None and image.size > 0:
                h, w = image.shape[:2]
                return Frame(
                    image=image,
                    timestamp=time.time(),
                    width=w,
                    height=h,
                )
            time.sleep(0.05)

        global _last_capture_error_log
        now = _time.time()
        if now - _last_capture_error_log >= _CAPTURE_ERROR_LOG_INTERVAL:
            logger.error("Failed to capture frame after retries (suppressing for 60s)")
            _last_capture_error_log = now
        return None
    
    def close(self):
        """Release the camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released")
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, *args):
        self.close()
