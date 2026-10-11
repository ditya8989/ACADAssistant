"""
ACAD Assistant - FastAPI Application Backend.
Academic AI Assistant for University Lecturers.
Implements:
1. Dashboard & Class Analytics (KPIs, Attendance trends, Heatmaps, Early Alerts)
2. Accessibility Scan Text to Speech (Document OCR + Web Speech)
3. AutoQuiz & Topic Mastery Detector (Difficulty Index P, Discrimination Index D, K-Means Clustering)
4. Chat AI Bot (RAG with Google Gemini)
5. Scan KTM Attendance (EasyOCR + ZXing Barcode + RapidFuzz + Anti-glare + Audio Feedback)
"""

import io
import os
import time
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database.db_manager import db
from modules.accessibility.doc_ocr import doc_ocr
from modules.attendance.scanner import ktm_scanner
from modules.chatbot.rag_engine import rag_engine
from modules.data_mining.psychometrics import PsychometricsEngine

# Initialize FastAPI app
app = FastAPI(
    title="ACAD Assistant API",
    description="Academic AI Assistant for Lecturers (PRD Implementation)",
    version="1.0.0"
)

# Enable CORS for flexible local development & mobile devices on LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


# --- Pydantic Request Models ---
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

class GenerateQuizRequest(BaseModel):
    topic: str
    material_text: Optional[str] = ""
    meeting_id: Optional[int] = 5
    count: Optional[int] = 3

class CreateQuizRequest(BaseModel):
    meeting_id: int
    title: str
    topic: str
    questions: List[Dict[str, Any]]

class SubmitQuizRequest(BaseModel):
    student_nim: str
    answers: Dict[str, str]

class ScanFrameRequest(BaseModel):
    frame_base64: str
    meeting_id: Optional[int] = None

class ToggleAttendanceRequest(BaseModel):
    meeting_id: int
    student_nim: str
    status: str # 'Hadir', 'Belum Hadir', 'Izin', 'Sakit'


# ==========================================
# 1. DASHBOARD & MONITORING ENDPOINTS (Fitur 1)
# ==========================================

@app.get("/api/dashboard")
def get_dashboard():
    """Returns complete KPI cards, attendance trends, quiz mastery, and early alert banners."""
    try:
        data = PsychometricsEngine.get_dashboard_summary()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/course")
def get_course():
    """Returns course metadata and meetings list."""
    course = db.get_course_info()
    meetings = db.get_all_meetings()
    active_m = db.get_active_meeting()
    return {
        "success": True,
        "course": course,
        "meetings": meetings,
        "active_meeting": active_m
    }

@app.post("/api/meetings/{meeting_id}/set-active")
def set_active_meeting(meeting_id: int):
    """Sets a specific meeting session as currently active."""
    success = db.set_active_meeting(meeting_id)
    return {"success": success, "active_meeting": db.get_active_meeting()}


# ==========================================
# 2. STUDENTS & CLUSTERING ENDPOINTS
# ==========================================

@app.get("/api/students")
def get_students():
    """Returns all 32 students in Kelas 07TPLP003 with attendance & quiz statistics."""
    clusters_info = PsychometricsEngine.get_student_risk_clusters()
    return {"success": True, "data": clusters_info}


# ==========================================
# 3. SCAN KTM & PRESENSI ENDPOINTS (Fitur 5)
# ==========================================

@app.get("/api/attendance")
def get_attendance(meeting_id: Optional[int] = None):
    """Returns current attendance status for all students in a meeting."""
    active_m = db.get_active_meeting()
    target_id = meeting_id or active_m.get("id", 1)
    records = db.get_meeting_attendance(target_id)
    hadir_count = sum(1 for r in records if r["status"] == "Hadir")
    return {
        "success": True,
        "meeting_id": target_id,
        "hadir_count": hadir_count,
        "total_count": len(records),
        "attendance": records
    }

@app.post("/api/attendance/scan-frame")
def scan_webcam_frame(req: ScanFrameRequest):
    """
    Receives base64 camera frame snapshot from browser.
    Processes via Barcode/ZXing, EasyOCR, CLAHE anti-glare, and RapidFuzz matcher.
    """
    result = ktm_scanner.scan_base64_frame(req.frame_base64, req.meeting_id)
    return {"success": True, "result": result}

@app.post("/api/attendance/upload-image")
async def scan_uploaded_image(file: UploadFile = File(...), meeting_id: Optional[int] = Form(None)):
    """Uploads a KTM photo or test sample image."""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Citra tidak dapat dibaca")
        result = ktm_scanner.scan_image(img, meeting_id)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/attendance/toggle")
def toggle_attendance(req: ToggleAttendanceRequest):
    """Manually toggles student attendance status."""
    success = db.toggle_manual_attendance(req.meeting_id, req.student_nim, req.status)
    return {"success": success}

class ResetStudentRequest(BaseModel):
    meeting_id: int
    student_nim: str

@app.post("/api/attendance/reset-student")
def reset_student_attendance(req: ResetStudentRequest):
    """Resets attendance for a specific student (e.g. Aditya) back to Belum Hadir for re-testing."""
    success = db.reset_student_attendance(req.meeting_id, req.student_nim)
    return {"success": success, "message": f"Status {req.student_nim} berhasil direset ke Belum Hadir"}

@app.post("/api/attendance/reset-meeting")
def reset_meeting_attendance(meeting_id: int = Query(...)):
    """Resets all attendance records in a meeting back to Belum Hadir."""
    success = db.reset_meeting_attendance(meeting_id)
    return {"success": success, "message": f"Presensi pertemuan {meeting_id} berhasil direset ke Belum Hadir"}

@app.get("/api/attendance/sample-scan/{sample_name}")
def scan_sample(sample_name: str, meeting_id: Optional[int] = None):
    """Utility endpoint to test built-in sample cards (e.g. sample_unpam_aditya.jpg)."""
    sample_path = os.path.join(os.path.dirname(__file__), "data", "samples", sample_name)
    if not os.path.exists(sample_path):
        sample_path = os.path.join("D:\\AbsensiTapKartu", sample_name)
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="File sample tidak ditemukan")

    img = cv2.imread(sample_path)
    result = ktm_scanner.scan_image(img, meeting_id)
    return {"success": True, "result": result}


# ==========================================
# 4. ACCESSIBILITY & TEXT-TO-SPEECH (Fitur 2)
# ==========================================

@app.post("/api/accessibility/ocr")
async def ocr_document(file: UploadFile = File(...)):
    """
    Extracts text from uploaded PDF document or photo for Text-to-Speech reading.
    Supports Bahasa Indonesia and English.
    """
    try:
        contents = await file.read()
        res = doc_ocr.extract_from_bytes(contents, file.filename or "file.pdf")
        return {"success": res.get("success", False), "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 5. AUTOQUIZ & DATA MINING (Fitur 3)
# ==========================================

@app.get("/api/quizzes")
def get_all_quizzes():
    """Returns all created quizzes with submission statistics."""
    quizzes = db.get_all_quizzes()
    return {"success": True, "quizzes": quizzes}

@app.get("/api/quizzes/{quiz_id}")
def get_quiz_details(quiz_id: int):
    """Returns quiz questions and student submissions."""
    quiz = db.get_quiz_by_id(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Kuis tidak ditemukan")
    analysis = PsychometricsEngine.analyze_quiz(quiz_id)
    return {"success": True, "quiz": quiz, "analytics": analysis}

@app.post("/api/quizzes/generate")
def generate_quiz(req: GenerateQuizRequest):
    """
    Generates 3-5 multiple-choice questions via Gemini based on topic or uploaded material text.
    """
    try:
        questions = rag_engine.generate_quiz(
            topic=req.topic,
            content_text=req.material_text or "",
            count=req.count or 3
        )
        return {"success": True, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quizzes/generate-from-pdf")
async def generate_quiz_from_pdf(
    file: UploadFile = File(...),
    meeting_id: int = Form(5),
    count: int = Form(3)
):
    """
    Generates 3-5 quiz questions directly from uploaded PDF lecture document.
    """
    try:
        contents = await file.read()
        ocr_res = doc_ocr.extract_from_bytes(contents, file.filename or "materi.pdf")
        material_text = ocr_res.get("text", "")
        if not material_text:
            raise HTTPException(status_code=400, detail="Tidak dapat mengekstrak teks dari file PDF")
        
        topic_guess = os.path.splitext(file.filename or "Materi Perkuliahan")[0]
        # Clean topic filename
        topic_guess = topic_guess.replace("_", " ").replace("-", " ")
        
        questions = rag_engine.generate_quiz(
            topic=topic_guess,
            content_text=material_text,
            count=count
        )
        return {
            "success": True,
            "filename": file.filename,
            "topic": topic_guess,
            "word_count": ocr_res.get("word_count", 0),
            "questions": questions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quizzes/create")
def create_quiz(req: CreateQuizRequest):
    """Saves approved quiz into the database."""
    quiz_id = db.create_quiz(
        meeting_id=req.meeting_id,
        title=req.title,
        topic=req.topic,
        questions=req.questions
    )
    return {"success": True, "quiz_id": quiz_id}

@app.post("/api/quizzes/{quiz_id}/submit")
def submit_quiz_answer(quiz_id: int, req: SubmitQuizRequest):
    """Records an individual student submission."""
    try:
        score, correct_count, total = db.submit_quiz_answer(
            quiz_id=quiz_id,
            student_nim=req.student_nim,
            answers=req.answers
        )
        return {
            "success": True,
            "score": score,
            "correct_count": correct_count,
            "total_questions": total
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/quizzes/{quiz_id}/simulate-class")
def simulate_class_quiz_responses(quiz_id: int, pass_rate: float = Query(0.75, ge=0.2, le=0.98)):
    """
    Simulates responses from all 32 students in Kelas 07TPLP003.
    Enables instant demonstration of Item Difficulty Index (P), Discrimination (D),
    and Anomaly Alerts!
    """
    import random
    quiz = db.get_quiz_by_id(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Kuis tidak ditemukan")

    students = db.get_all_students()
    questions = quiz.get("questions", [])

    for idx, st in enumerate(students):
        answers = {}
        for q in questions:
            # Capability distribution
            prob = pass_rate
            if idx < 10:
                prob = min(0.96, prob + 0.20)
            elif idx > 22:
                prob = max(0.20, prob - 0.25)

            is_correct = random.random() < prob
            if is_correct:
                chosen = q["correct"]
            else:
                wrong_opts = [o[0] for o in q["options"] if o[0] != q["correct"]]
                chosen = random.choice(wrong_opts) if wrong_opts else "A"
            answers[str(q["id"])] = chosen

        db.submit_quiz_answer(quiz_id, st["nim"], answers)

    # Return updated analytics
    analysis = PsychometricsEngine.analyze_quiz(quiz_id)
    return {"success": True, "message": f"Berhasil mensimulasikan {len(students)} respons mahasiswa", "analytics": analysis}


# ==========================================
# 6. CHAT AI BOT ENDPOINTS (Fitur 4)
# ==========================================

@app.post("/api/chat")
def chat_ai(req: ChatRequest):
    """
    Conversational AI grounded in real class data via Gemini RAG.
    """
    try:
        reply = rag_engine.chat(req.message, req.history)
        return {
            "success": True,
            "reply": reply,
            # Audio cue text stripped of markdown for smooth browser TTS speech
            "speech_text": reply.replace("*", "").replace("#", "").replace("`", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 7. STATIC FILES & FRONTEND SERVING
# ==========================================

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({
        "status": "online",
        "message": "ACAD Assistant API is running! Frontend is initializing."
    })

# Mount remaining static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
