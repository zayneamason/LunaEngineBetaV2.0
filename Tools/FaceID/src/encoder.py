"""
FaceID Encoder Module
=====================

Detects faces and produces embeddings using FaceNet (MobileFaceNet variant).
Uses facenet-pytorch's MTCNN for detection and InceptionResnetV1 for embeddings.

MobileFaceNet: ~7MB model, 128-dim embeddings, optimized for edge devices.
Everything runs locally. No cloud. No data leaves the device.
"""

import numpy as np
import torch
import logging
import time
from dataclasses import dataclass
from typing import Optional
from PIL import Image

from facenet_pytorch import MTCNN, InceptionResnetV1

logger = logging.getLogger(__name__)


@dataclass
class FaceDetection:
    """A detected face with its embedding."""
    embedding: np.ndarray           # 512-dim float32 (L2-normalized)
    bbox: tuple[int, int, int, int] # x, y, w, h in frame
    confidence: float               # 0-1 detection confidence
    face_image: Optional[np.ndarray] = None  # Cropped face (for preview)
    timestamp: float = 0.0


class FaceEncoder:
    """
    Detects faces and produces embeddings using FaceNet.
    
    Uses MTCNN for face detection and InceptionResnetV1 pretrained
    on VGGFace2 for embeddings.
    
    All processing happens on-device (CPU for M1 compatibility).
    """
    
    # Detection thresholds
    MIN_FACE_SIZE = 20              # Minimum face pixel width
    DETECTION_THRESHOLD = 0.5       # MTCNN confidence threshold (relaxed for MacBook cameras)
    
    def __init__(self):
        logger.info("Initializing FaceEncoder (FaceNet MobileFaceNet)...")
        
        # Use CPU — MPS (Apple Silicon GPU) has issues with MTCNN
        self.device = torch.device('cpu')
        
        # MTCNN for face detection + alignment
        self.detector = MTCNN(
            image_size=160,
            margin=20,
            min_face_size=self.MIN_FACE_SIZE,
            thresholds=[0.4, 0.5, 0.5],    # Detection thresholds per stage (relaxed)
            factor=0.709,
            post_process=True,
            device=self.device,
            keep_all=True,                   # Detect multiple faces
        )
        
        # InceptionResnetV1 for embeddings (pretrained on VGGFace2)
        self.encoder = InceptionResnetV1(
            pretrained='vggface2',
            classify=False,
            device=self.device,
        ).eval()
        
        logger.info("FaceEncoder ready")
    
    def detect_faces(self, frame: np.ndarray) -> list[FaceDetection]:
        """
        Detect all faces in a BGR frame and produce embeddings.
        
        Args:
            frame: BGR numpy array from OpenCV
            
        Returns:
            List of FaceDetection objects with embeddings
        """
        # Convert BGR (OpenCV) to RGB (PIL/FaceNet)
        rgb = frame[:, :, ::-1]
        pil_image = Image.fromarray(rgb)
        
        # Detect faces — get aligned face tensors and bounding boxes
        try:
            faces, probs = self.detector(pil_image, return_prob=True)
        except Exception as e:
            logger.debug(f"Detection failed: {e}")
            return []
        
        if faces is None:
            return []
        
        # Get bounding boxes separately
        boxes, _ = self.detector.detect(pil_image)
        
        results = []
        
        # Handle single face (detector returns tensor, not list)
        if faces.dim() == 3:
            faces = faces.unsqueeze(0)
            probs = [probs] if not hasattr(probs, '__len__') else probs
        
        for i, (face_tensor, prob) in enumerate(zip(faces, probs)):
            if prob is None or prob < self.DETECTION_THRESHOLD:
                continue
            
            # Get embedding
            with torch.no_grad():
                embedding = self.encoder(face_tensor.unsqueeze(0))
            
            emb_np = embedding.squeeze().numpy()
            
            # L2 normalize
            norm = np.linalg.norm(emb_np)
            if norm > 0:
                emb_np = emb_np / norm
            
            # Extract bounding box
            bbox = (0, 0, 0, 0)
            if boxes is not None and i < len(boxes):
                b = boxes[i].astype(int)
                bbox = (int(b[0]), int(b[1]), int(b[2] - b[0]), int(b[3] - b[1]))
            
            # Crop face for preview
            face_crop = None
            if bbox[2] > 0 and bbox[3] > 0:
                x, y, w, h = bbox
                y1 = max(0, y)
                y2 = min(frame.shape[0], y + h)
                x1 = max(0, x)
                x2 = min(frame.shape[1], x + w)
                face_crop = frame[y1:y2, x1:x2].copy()
            
            results.append(FaceDetection(
                embedding=emb_np,
                bbox=bbox,
                confidence=float(prob),
                face_image=face_crop,
                timestamp=time.time(),
            ))
        
        return results
    
    @property
    def embedding_dim(self) -> int:
        """Dimension of the embedding vectors."""
        return 512  # InceptionResnetV1 produces 512-dim
    
    @property
    def model_name(self) -> str:
        return "facenet_vggface2"
