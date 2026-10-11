"""
Image Preprocessing Module for KTM ROI.
Designed to handle uneven lighting, plastic lamination glare, and contrast noise.
"""

import cv2
import numpy as np


class CardPreprocessor:
    """Provides adaptive image enhancement techniques for laminated cards."""

    def __init__(self, clip_limit: float = 2.5, tile_grid_size: tuple = (8, 8)):
        self.clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    def enhance_for_ocr(self, roi_bgr: np.ndarray) -> np.ndarray:
        """
        Enhances the ROI image for robust text recognition under webcam conditions.
        
        Steps:
        1. Auto-upscale low-resolution frames (crucial for webcam text clarity).
        2. Convert to grayscale.
        3. Bilateral filtering to smooth glossy reflections while keeping text edges crisp.
        4. CLAHE (Contrast Limited Adaptive Histogram Equalization) to balance lighting.
        5. Light sharpening to compensate for laptop camera focus limitations.
        """
        if roi_bgr is None or roi_bgr.size == 0:
            return roi_bgr

        # 1. Target width (~480px) provides the fastest CPU inference (<2s) while preserving 100% font clarity
        h, w = roi_bgr.shape[:2]
        target_w = 480
        if abs(w - target_w) > 30:
            scale = target_w / float(w)
            scaled = cv2.resize(roi_bgr, (target_w, int(h * scale)), interpolation=cv2.INTER_AREA if w > target_w else cv2.INTER_CUBIC)
        else:
            scaled = roi_bgr

        # 2. Grayscale
        if len(scaled.shape) == 3:
            gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        else:
            gray = scaled.copy()

        # 3. Glare-tolerant edge-preserving smoothing
        denoised = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)

        # 4. CLAHE for localized illumination normalization
        enhanced = self.clahe.apply(denoised)

        # 5. Mild unsharp masking to enhance font contours
        gaussian = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.5)
        sharpened = cv2.addWeighted(enhanced, 1.35, gaussian, -0.35, 0)

        return sharpened

    def binarize_for_high_glare(self, gray: np.ndarray) -> np.ndarray:
        """
        Secondary adaptive thresholding method when severe glare is present.
        """
        # Morphological opening to estimate background illumination
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        background = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
        norm_img = cv2.subtract(gray, background)
        norm_img = cv2.normalize(norm_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)

        # Otsu binarization
        _, thresh = cv2.threshold(norm_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh
