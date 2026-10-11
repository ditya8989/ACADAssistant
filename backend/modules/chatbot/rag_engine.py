"""
RAG Engine & AI Assistant for ACAD Assistant (Fitur 4: Chat AI Bot & Fitur 3: AutoQuiz Generator).
Connects to Google Gemini API using GEMINI_API_KEY with local academic database context injection.
Includes offline intelligent fallback if disconnected.
"""

import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional
from database.db_manager import db
from modules.data_mining.psychometrics import PsychometricsEngine


MODELS_PRIORITY = [
    "models/gemini-3.5-flash-lite",
    "models/gemini-3.5-flash",
    "models/gemini-3.8-flash"
]


class RAGEngine:
    """Retrieval-Augmented Generation engine for university lecturer assistant."""

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")

    def _call_gemini(self, prompt: str, system_instruction: str = "") -> str:
        """Invokes Gemini API with prioritized fallback models."""
        if not self.api_key:
            return ""

        for model_name in MODELS_PRIORITY:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={self.api_key}"
            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 2048
                }
            }
            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
            except Exception as e:
                # Try next model
                continue

        return ""

    def build_rag_context(self) -> str:
        """Retrieves and formats rich class data into LLM context."""
        course = db.get_course_info()
        students = db.get_all_students()
        meetings = db.get_all_meetings()
        active_meeting = db.get_active_meeting()
        clusters = PsychometricsEngine.get_student_risk_clusters()
        dashboard = PsychometricsEngine.get_dashboard_summary()

        # Build attendance < 75% list
        low_att_students = [
            s for s in clusters.get("students", [])
            if s.get("attendance_rate", 100) < 75.0
        ]

        # Build at-risk list
        at_risk_students = clusters.get("clusters", {}).get("At-Risk", [])

        # Critical subtopics
        crit_topics = dashboard.get("critical_subtopics", [])

        context_lines = [
            f"=== PROFIL KELAS & MATA KULIAH ===",
            f"Mata Kuliah: {course.get('name')} ({course.get('code')})",
            f"Kelas: {course.get('class_code')} | SKS: {course.get('sks')} | Prodi: {course.get('prodi')}",
            f"Semester: {course.get('semester')} ({course.get('academic_year')})",
            f"Total Mahasiswa Terdaftar: {len(students)} orang (NIM 23101140xxxx & 22101140xxxx)",
            f"Pertemuan Aktif Saat Ini: Pertemuan {active_meeting.get('meeting_no')} - {active_meeting.get('topic')}",
            "",
            f"=== RINGKASAN METRIK & DATA MINING ===",
            f"Tingkat Presensi Minggu Ini: {dashboard.get('kpi', {}).get('weekly_attendance_rate')}% ({dashboard.get('kpi', {}).get('hadir_count')}/{len(students)} mahasiswa)",
            f"Segmen Klaster Mahasiswa (K-Means):",
            f" - Mastered: {clusters.get('counts', {}).get('mastered', 0)} mahasiswa",
            f" - Borderline: {clusters.get('counts', {}).get('borderline', 0)} mahasiswa",
            f" - At-Risk (Butuh Remedial): {clusters.get('counts', {}).get('at_risk', 0)} mahasiswa",
            "",
            f"=== DAFTAR MAHASISWA PRESENSI RENDAH (< 75%) ===",
        ]

        if low_att_students:
            for s in low_att_students:
                context_lines.append(f"- NIM: {s['nim']} | Nama: {s['name']} | Kehadiran: {s['attendance_rate']}% | Rerata Kuis: {s['quiz_avg']}")
        else:
            context_lines.append("(Tidak ada, seluruh mahasiswa memiliki kehadiran >= 75%)")

        context_lines.append("")
        context_lines.append("=== DAFTAR MAHASISWA AT-RISK (PRIORITAS REMEDIAL) ===")
        if at_risk_students:
            for s in at_risk_students:
                context_lines.append(f"- NIM: {s['nim']} | Nama: {s['name']} | Kehadiran: {s['attendance_rate']}% | Rerata Kuis: {s['quiz_avg']} | Cluster: At-Risk")
        else:
            context_lines.append("(Tidak ada mahasiswa berstatus at-risk)")

        context_lines.append("")
        context_lines.append("=== TOPIK & MATERI KRITIS (Difficulty P < 0.40) ===")
        if crit_topics:
            for t in crit_topics:
                context_lines.append(f"- Subtopik: '{t.get('subtopic')}' (Indeks Kesulitan P={t.get('difficulty_p')}, Daya Pembeda D={t.get('discrimination_d')})")
        else:
            context_lines.append("(Semua topik yang telah diuji memiliki tingkat kesulitan normal/tercapai)")

        return "\n".join(context_lines)

    def chat(self, user_query: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """Answers user question with RAG-grounded insights."""
        context = self.build_rag_context()

        system_instruction = (
            "Anda adalah ACAD Assistant, asisten kecerdasan buatan akademis khusus untuk Dosen pengampu perguruan tinggi. "
            "Anda memiliki akses langsung ke basis data kelas, metrik presensi KTM, hasil AutoQuiz, dan analisis penambangan data psikometrik (Item Difficulty P, Discrimination D, dan Klastering K-Means At-Risk). "
            "Berikan jawaban yang ramah, profesional, ringkas, solutif, berbasis data nyata kelas yang tertera pada konteks. "
            "Gunakan format Markdown yang rapi (bullet points, bold text). Jawablah selalu dalam Bahasa Indonesia."
        )

        history_text = ""
        if history:
            for h in history[-4:]:
                role = "Dosen" if h.get("role") == "user" else "Asisten"
                history_text += f"{role}: {h.get('content')}\n"

        prompt = f"""
KONTEKS DATA KELAS TERBARU:
{context}

RIWAYAT PERCAKAPAN:
{history_text}

PERTANYAAN DOSEN:
{user_query}

JAWABAN ACAD ASSISTANT:
"""
        response_text = self._call_gemini(prompt, system_instruction)

        if not response_text:
            # Smart Offline Fallback
            response_text = self._offline_chat_fallback(user_query)

        return response_text

    def _offline_chat_fallback(self, query: str) -> str:
        """Deterministic rule-based reply if offline or API limit reached."""
        q_lower = query.lower()
        clusters = PsychometricsEngine.get_student_risk_clusters()
        dashboard = PsychometricsEngine.get_dashboard_summary()

        if "bawah 75" in q_lower or "< 75" in q_lower or "kehadiran" in q_lower or "absen" in q_lower:
            low_att = [s for s in clusters.get("students", []) if s.get("attendance_rate", 100) < 75.0]
            if low_att:
                res = "Berikut adalah daftar mahasiswa dengan tingkat kehadiran **di bawah 75%** di kelas Manajemen Proyek Informatika (07TPLP003):\n\n"
                for s in low_att:
                    res += f"- **{s['name']}** (NIM: `{s['nim']}`) — Kehadiran: `{s['attendance_rate']}%` (Hadir {s['hadir_count']}/{s['total_meetings']} sesi)\n"
                res += "\n💡 *Saran:* Berikan peringatan dini kehadiran agar mahasiswa tidak terkena pencekalan ujian akhir."
                return res
            return "Seluruh mahasiswa di kelas saat ini memiliki persentase kehadiran di atas 75%."

        if "at-risk" in q_lower or "berisiko" in q_lower or "remedial" in q_lower:
            at_risk = clusters.get("clusters", {}).get("At-Risk", [])
            res = f"Berdasarkan analisis klastering **K-Means**, terdapat **{len(at_risk)} mahasiswa** dalam kategori **At-Risk** (berisiko tinggi):\n\n"
            for s in at_risk:
                res += f"- **{s['name']}** (NIM: `{s['nim']}`) — Rerata Kuis: `{s['quiz_avg']}` | Kehadiran: `{s['attendance_rate']}%`\n"
            res += "\n💡 *Rekomendasi Tindakan:* Jadwalkan sesi tutorial singkat atau kuis remedial terarah pada subtopik kritis."
            return res

        if "kritis" in q_lower or "sulit" in q_lower or "review" in q_lower or "wbs" in q_lower:
            crit = dashboard.get("critical_subtopics", [])
            res = "Berdasarkan **Item Difficulty Index ($P < 0.40$)**, topik yang paling membutuhkan review kelas adalah:\n\n"
            for t in crit:
                res += f"- **{t['subtopic']}** (Indeks $P = {t['difficulty_p']}$)\n"
            res += "\n💡 *Evaluasi Materi:* Subtopik ini terbukti belum dikuasai mayoritas mahasiswa pada kuis sebelumnya. Disarankan membuka sesi diskusi 10 menit di awal perkuliahan berikutnya."
            return res

        return (
            "Halo Bapak/Ibu Dosen! Saya **ACAD Assistant**.\n\n"
            "Saya siap membantu Anda memantau:\n"
            "- Rekap presensi tatap muka dan mahasiswa presensi rendah (<75%)\n"
            "- Deteksi mahasiswa *At-Risk* via K-Means Clustering\n"
            "- Analisis topik kritis (*Need Review*) hasil kuis kilat\n"
            "- Rekomendasi materi remedial dan kisi-kisi ujian\n\n"
            "Silakan ketik pertanyaan spesifik seputar kelas Anda!"
        )

    def generate_quiz(self, topic: str, content_text: str = "", count: int = 3) -> List[Dict[str, Any]]:
        """Generates multiple-choice quiz questions with subtopics and explanations."""
        system_instruction = (
            "Anda adalah pembuat soal kuis perkuliahan (AutoQuiz Engine) untuk mata kuliah Manajemen Proyek Informatika. "
            "Keluarkan output HANYA berupa JSON valid tanpa markdown formatting tambahan atau pembungkus lain. "
            "Format JSON harus berupa array of objects dengan struktur: "
            "[{\"id\": 1, \"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"correct\": \"A\", \"subtopic\": \"...\", \"explanation\": \"...\"}]"
        )

        prompt = f"""
Buatkan {count} butir soal pilihan ganda (4 opsi: A, B, C, D) untuk mahasiswa semester 7 perguruan tinggi.
Topik Pertemuan: {topic}
Bahan Materi / Referensi:
{content_text[:2000] if content_text else 'Silabus standar Manajemen Proyek Informatika (SDLC, WBS, Scheduling, Cost EVA, Risk Mitigation)'}

Persyaratan:
- Soal harus relevan, aplikatif, dan memetakan sub-topik secara spesifik.
- Keluarkan HANYA JSON array valid!
"""
        raw_output = self._call_gemini(prompt, system_instruction)

        parsed_questions = []
        if raw_output:
            try:
                # Clean code blocks if present
                clean_json = re.sub(r"```json|```", "", raw_output).strip()
                data = json.loads(clean_json)
                if isinstance(data, list):
                    parsed_questions = data
            except Exception:
                pass

        if not parsed_questions:
            # Fallback deterministic template
            parsed_questions = [
                {
                    "id": 1,
                    "question": f"Dalam konteks '{topic}', apakah sasaran utama yang ingin dicapai oleh manajer proyek?",
                    "options": [
                        "A. Menyelesaikan seluruh deliverables sesuai batasan Scope, Time, dan Cost",
                        "B. Memaksimalkan penambahan fitur baru tanpa persetujuan stakeholder",
                        "C. Mengurangi dokumentasi teknis seminimal mungkin",
                        "D. Mengeliminasi seluruh risiko proyek menjadi nol mutlak"
                    ],
                    "correct": "A",
                    "subtopic": f"Prinsip Dasar {topic}",
                    "explanation": "Manajer proyek bertanggung jawab mencapai deliverables sesuai batasan Triple Constraint."
                },
                {
                    "id": 2,
                    "question": f"Indikator kunci keberhasilan evaluasi pada '{topic}' adalah?",
                    "options": [
                        "A. Jumlah baris kode yang ditulis programmer per hari",
                        "B. Tingkat kepatuhan jadwal dan kualitas hasil kerja terhadap baseline",
                        "C. Penggantian metodologi setiap minggu",
                        "D. Menghindari evaluasi berkala bersama klien"
                    ],
                    "correct": "B",
                    "subtopic": f"Metrik Kinerja {topic}",
                    "explanation": "Kinerja proyek diukur dari kesesuaian progres aktual terhadap baseline rencana kerja yang disepakati."
                },
                {
                    "id": 3,
                    "question": f"Langkah preventif utama saat terjadi hambatan tak terduga pada '{topic}' adalah?",
                    "options": [
                        "A. Melakukan eskalasi dan analisis akar masalah (Root Cause Analysis)",
                        "B. Mengabaikan kendala sampai batas waktu penyerahan akhir",
                        "C. Mengganti seluruh anggota tim secara sepihak",
                        "D. Menolak berkomunikasi dengan sponsor proyek"
                    ],
                    "correct": "A",
                    "subtopic": f"Mitigasi Kendala {topic}",
                    "explanation": "Analisis akar masalah (Root Cause Analysis) diperlukan untuk menentukan tindakan korektif yang tepat sasaran."
                }
            ]

        return parsed_questions


rag_engine = RAGEngine()
