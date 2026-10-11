"""
OCR Engine Module for AutoAttendance KTM Scanner.
Wraps EasyOCR with CPU inference backend.
"""

from typing import Any, List, Tuple
import numpy as np


class OCREngine:
    """Wrapper for EasyOCR reader optimized for CPU inference."""

    def __init__(self, languages: List[str] = None, gpu: bool = False):
        if languages is None:
            # English model contains all standard Latin characters A-Z, 0-9 and runs 10x faster on CPU
            languages = ["en"]
        self.languages = languages
        self.gpu = gpu
        self._reader = None

    @property
    def reader(self):
        """Lazy-loads the EasyOCR Reader instance."""
        if self._reader is None:
            import os
            import warnings
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=FutureWarning)
            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["PYTHONUTF8"] = "1"
            import easyocr
            print("[OCR] Menginisialisasi EasyOCR Reader (CPU mode)...")
            self._reader = easyocr.Reader(self.languages, gpu=self.gpu, verbose=False)
            print("[OCR] EasyOCR Reader siap digunakan.")
        return self._reader

    def extract_text(self, image: np.ndarray, detail: int = 1) -> List[Any]:
        """
        Extracts text from an image (BGR or Grayscale) using fast CPU settings.
        
        Args:
            image: numpy array frame of the ROI
            detail: 1 returns [(bbox, text, prob), ...], 0 returns [text, ...]
            
        Returns:
            List of detected text items.
        """
        if image is None or image.size == 0:
            return []

        try:
            # mag_ratio=1.0 and batch_size=6 significantly accelerate CPU inference
            results = self.reader.readtext(
                image,
                detail=detail,
                mag_ratio=1.0,
                batch_size=6,
                text_threshold=0.35,
                low_text=0.25,
                paragraph=False
            )
            return results
        except Exception as e:
            print(f"[OCR] Error during text recognition: {e}")
            return []

    def extract_clean_lines(self, image: np.ndarray, min_conf: float = 0.08) -> Tuple[List[str], List[Any]]:
        """
        Convenience method returning filtered clean text lines above minimum confidence.
        
        Returns:
            (clean_text_lines, raw_detections)
        """
        detections = self.extract_text(image, detail=1)
        clean_lines = []
        for item in detections:
            # EasyOCR detail=1 returns (bbox, text, prob)
            if len(item) >= 3:
                bbox, text, prob = item[0], item[1], item[2]
                text_str = str(text).strip()
                if prob >= min_conf and len(text_str) > 0:
                    clean_lines.append(text_str)
            elif len(item) == 2:
                text_str = str(item[0]).strip()
                if len(text_str) > 0:
                    clean_lines.append(text_str)

        return clean_lines, detections
