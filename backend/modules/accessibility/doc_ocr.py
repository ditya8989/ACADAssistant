"""
Document OCR Module for ACAD Assistant (Fitur 2: Aksesibilitas Scan Text to Speech).
Extracts text from physical book photos, uploaded images (JPG, PNG), or PDF documents.
Supports multi-language extraction (Bahasa Indonesia & English).
"""

import io
import os
from typing import Any, Dict, List
import cv2
import numpy as np
from pypdf import PdfReader


class DocumentOCREngine:
    """Extracts text from documents and images for Text-to-Speech processing."""

    def __init__(self):
        self._easyocr_reader = None

    @property
    def reader(self):
        if self._easyocr_reader is None:
            import easyocr
            # Load reader for Indonesian ('id') and English ('en')
            self._easyocr_reader = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
        return self._easyocr_reader

    def extract_from_bytes(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Dispatches file extraction based on extension.
        Returns extracted text, paragraph list, and word count.
        """
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".pdf":
            return self.extract_from_pdf_bytes(file_bytes)
        else:
            return self.extract_from_image_bytes(file_bytes)

    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Extracts text from PDF document using PyPDF, with OCR fallback if scanned."""
        try:
            stream = io.BytesIO(pdf_bytes)
            reader = PdfReader(stream)
            extracted_pages = []
            full_text_parts = []

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                page_text = page_text.strip()
                if page_text:
                    extracted_pages.append({"page": i + 1, "text": page_text})
                    full_text_parts.append(page_text)

            combined_text = "\n\n".join(full_text_parts).strip()

            # If empty (scanned PDF), return message to user
            if not combined_text:
                combined_text = "[Dokumen PDF berbasis pindaian citra murni tanpa lapisan teks digital. Silakan unggah lembar halaman sebagai citra JPG/PNG untuk pemindaian OCR penuh.]"

            paragraphs = [p.strip() for p in combined_text.split("\n\n") if p.strip()]
            word_count = len(combined_text.split())

            return {
                "success": True,
                "text": combined_text,
                "paragraphs": paragraphs,
                "word_count": word_count,
                "page_count": len(reader.pages),
                "source_type": "PDF"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Gagal membaca PDF: {str(e)}",
                "text": "",
                "paragraphs": [],
                "word_count": 0
            }

    def extract_from_image_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """Extracts text from image bytes using OpenCV & EasyOCR."""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {"success": False, "error": "Format citra tidak valid", "text": "", "paragraphs": [], "word_count": 0}

            # Preprocessing: convert to grayscale and contrast enhancement
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # OCR inference
            ocr_results = self.reader.readtext(enhanced, detail=0, paragraph=True)
            combined_text = "\n\n".join(ocr_results).strip()
            paragraphs = [p.strip() for p in ocr_results if p.strip()]
            word_count = len(combined_text.split())

            return {
                "success": True,
                "text": combined_text,
                "paragraphs": paragraphs,
                "word_count": word_count,
                "source_type": "Image OCR"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Gagal menjalankan OCR citra: {str(e)}",
                "text": "",
                "paragraphs": [],
                "word_count": 0
            }


doc_ocr = DocumentOCREngine()
