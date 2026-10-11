"""
Barcode & QR Code Scanner Engine.
Uses zxing-cpp for high-speed, zero-dependency 1D/2D barcode and QR code decoding (<50ms).
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

try:
    import zxingcpp
    HAVE_ZXING = True
except ImportError:
    HAVE_ZXING = False


class BarcodeScanner:
    """Fast, real-time 1D/2D Barcode and QR code scanner for KTM cards."""

    def __init__(self):
        self.available = HAVE_ZXING
        if not self.available:
            print("[BARCODE] Warning: zxing-cpp tidak terpasang. Scanner barcode dinonaktifkan.")

    def scan(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Decodes all barcodes/QR codes present in the image.
        Returns list of dicts with keys: 'text', 'format', 'nim_candidate', 'points'
        """
        if not self.available or image is None or image.size == 0:
            return []

        try:
            # Grayscale conversion provides 25-30% faster C++ decoding
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            results = zxingcpp.read_barcodes(gray)
            parsed = []
            for r in results:
                raw_text = r.text.strip()
                if not raw_text:
                    continue

                # Extract digits/NIM candidate if text is a URL or formatted string
                digits_only = re.findall(r"\d{6,14}", raw_text)
                nim_candidate = digits_only[0] if digits_only else raw_text

                # Position polygon/points if available
                points = None
                if hasattr(r, 'position') and r.position is not None:
                    try:
                        p = r.position
                        points = np.array([
                            [p.top_left.x, p.top_left.y],
                            [p.top_right.x, p.top_right.y],
                            [p.bottom_right.x, p.bottom_right.y],
                            [p.bottom_left.x, p.bottom_left.y]
                        ], dtype=np.int32)
                    except Exception:
                        points = None

                parsed.append({
                    "text": raw_text,
                    "format": str(r.format),
                    "nim_candidate": nim_candidate,
                    "points": points
                })
            return parsed
        except Exception as e:
            print(f"[BARCODE] Scan error: {e}")
            return []

    def draw_barcode_highlights(self, frame: np.ndarray, barcodes: List[Dict[str, Any]], offset: Tuple[int, int] = (0, 0)) -> np.ndarray:
        """Draws glowing highlight polygons around detected barcodes on the camera feed."""
        ox, oy = offset
        for b in barcodes:
            pts = b.get("points")
            if pts is not None:
                shifted = pts + np.array([ox, oy])
                cv2.polylines(frame, [shifted], isClosed=True, color=(0, 255, 255), thickness=2)
                # Draw label badge
                cv2.putText(frame, f"QR: {b.get('nim_candidate')}", (shifted[0][0], max(20, shifted[0][1] - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        return frame
