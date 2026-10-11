"""
KTM Attendance Scanner Service.
Coordinates:
1. Barcode / QR Scanner (Fast Path, <20ms)
2. Preprocessor (Bilateral filter + CLAHE anti-glare)
3. EasyOCR Text Extraction (Optimized scale & multi-thread CPU)
4. Dual-path Matcher (Deterministic NIM + RapidFuzz Name >= 70%)
5. Database Recording & Duplicate Prevention (FR-04)
"""

import base64
from datetime import datetime
import io
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from database.db_manager import db
from modules.attendance.barcode_engine import BarcodeScanner
from modules.attendance.matcher import AttendanceMatcher
from modules.attendance.ocr_engine import OCREngine
from modules.attendance.preprocessor import CardPreprocessor


class KTMScannerService:
    """Unified KTM recognition engine for live camera feeds and image uploads."""

    def __init__(self):
        self.preprocessor = CardPreprocessor()
        self.barcode_scanner = BarcodeScanner()
        self.ocr_engine = OCREngine(languages=["en"], gpu=False)
        # Initialize matcher with students from database
        students = db.get_all_students()
        self.matcher = AttendanceMatcher(students, fuzzy_threshold=70.0)
        
        # Warmup EasyOCR in background thread so user gets 0s cold start delay
        threading.Thread(target=self._warmup_ocr, daemon=True).start()

    def _warmup_ocr(self):
        """Warmup model weights into CPU memory."""
        try:
            dummy = np.zeros((100, 200, 3), dtype=np.uint8)
            self.ocr_engine.extract_text(dummy, detail=0)
        except Exception:
            pass

    def refresh_students(self):
        """Refreshes student list in matcher cache."""
        students = db.get_all_students()
        self.matcher.update_records(students)

    def scan_image(
        self,
        image_bgr: np.ndarray,
        meeting_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes complete recognition pipeline on a BGR image frame.
        Optimized for <2s inference by auto-scaling and fast-path barcode triage.
        """
        if image_bgr is None or image_bgr.size == 0:
            return {
                "success": False,
                "message": "Citra tidak valid / kosong",
                "detected": False,
                "student": None,
                "raw_texts": []
            }

        start_time = time.time()
        active_meeting = db.get_active_meeting()
        target_meeting_id = meeting_id or active_meeting.get("id", 1)

        # Ensure matcher cache has latest records
        self.refresh_students()

        # Optimize size: Scale to standard width of 640px if larger (speeds up CPU inference 3x)
        h, w = image_bgr.shape[:2]
        if w > 640:
            scale = 640.0 / w
            proc_img = cv2.resize(image_bgr, (640, int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            proc_img = image_bgr

        raw_texts: List[str] = []
        matched_nim: Optional[str] = None
        matched_method: str = ""
        matched_conf: float = 0.0

        # --- STEP 1: Fast Barcode / QR Code Scan (<20ms) ---
        barcode_results = self.barcode_scanner.scan(proc_img)
        for b in barcode_results:
            cand = b.get("nim_candidate", "")
            raw_texts.append(f"[BARCODE] {cand}")
            # Check candidate directly against database NIMs
            if cand in self.matcher.nim_map:
                matched_nim = cand
                matched_method = f"Barcode ({b.get('format', 'QR')})"
                matched_conf = 100.0
                break

        # --- STEP 2: OCR Fallback if Barcode did not match ---
        if not matched_nim:
            # Apply anti-glare preprocessing
            enhanced = self.preprocessor.enhance_for_ocr(proc_img)

            # OCR inference
            ocr_results = self.ocr_engine.extract_text(enhanced, detail=1)

            # Collect raw text lines
            extracted_lines = []
            for item in ocr_results:
                if len(item) >= 2:
                    t = str(item[1]).strip()
                    if t:
                        extracted_lines.append(t)
                        raw_texts.append(t)

            # Execute dual-path matching (NIM Priority + RapidFuzz Name)
            if extracted_lines:
                match_result = self.matcher.match(extracted_lines)
                if match_result and match_result.get("matched"):
                    matched_nim = match_result.get("nim")
                    matched_method = match_result.get("method", "OCR")
                    matched_conf = match_result.get("confidence", 85.0)

        elapsed_ms = round((time.time() - start_time) * 1000, 1)

        # --- STEP 3: Record Attendance & Check Duplication ---
        if matched_nim:
            student_info = self.matcher.nim_map.get(matched_nim, {})
            student_name = student_info.get("name") or student_info.get("Nama") or ""

            success, db_msg, rec_info = db.record_attendance(
                meeting_id=target_meeting_id,
                student_nim=matched_nim,
                method=matched_method
            )

            already_attended = (db_msg == "Sudah Melakukan Presensi")
            status_text = "Hadir" if (success or already_attended) else "Belum Hadir"
            recorded_time = rec_info.get("timestamp") if rec_info else datetime.now().strftime("%H:%M:%S")

            return {
                "success": True,
                "detected": True,
                "already_attended": already_attended,
                "message": "PRESENSI BERHASIL!" if success else "SUDAH MELAKUKAN PRESENSI",
                "student": {
                    "nim": matched_nim,
                    "name": student_name,
                    "status": status_text,
                    "timestamp": recorded_time,
                    "method": matched_method,
                    "confidence": matched_conf
                },
                "raw_texts": raw_texts[:6],
                "elapsed_ms": elapsed_ms
            }

        return {
            "success": False,
            "detected": False,
            "already_attended": False,
            "message": "KARTU BELUM TERDETEKSI" if not raw_texts else "KARTU TIDAK DIKENALI",
            "student": None,
            "raw_texts": raw_texts[:6],
            "elapsed_ms": elapsed_ms
        }

    def scan_base64_frame(self, base64_str: str, meeting_id: Optional[int] = None) -> Dict[str, Any]:
        """Decodes base64 data url from web frontend and runs scanner."""
        try:
            if "," in base64_str:
                base64_str = base64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(base64_str)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return self.scan_image(img_bgr, meeting_id)
        except Exception as e:
            return {
                "success": False,
                "detected": False,
                "message": f"Gagal membaca frame: {str(e)}",
                "student": None,
                "raw_texts": []
            }


# Singleton service
ktm_scanner = KTMScannerService()
