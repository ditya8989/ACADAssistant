"""
Database Manager for ACAD Assistant.
Manages SQLite storage for Students, Meetings, Attendance, Quizzes, Submissions, and Psychometrics.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "acad_assistant.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mahasiswa.csv")


class DatabaseManager:
    """Thread-safe SQLite manager for ACAD Assistant."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self) -> None:
        """Initializes tables and seeds initial data from mahasiswa.csv."""
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()

            # 1. Course Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                class_code TEXT NOT NULL,
                prodi TEXT NOT NULL,
                semester INTEGER NOT NULL,
                academic_year TEXT NOT NULL,
                sks INTEGER NOT NULL
            )
            """)

            # 2. Students Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                nim TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                class_code TEXT NOT NULL
            )
            """)

            # 3. Meetings Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY,
                meeting_no INTEGER NOT NULL,
                topic TEXT NOT NULL,
                date_str TEXT NOT NULL,
                status TEXT NOT NULL -- 'completed', 'active', 'upcoming'
            )
            """)

            # 4. Attendance Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                student_nim TEXT NOT NULL,
                status TEXT NOT NULL, -- 'Hadir', 'Belum Hadir', 'Izin', 'Sakit'
                timestamp TEXT,
                method TEXT, -- 'NIM Exact', 'Nama Fuzzy', 'Barcode/QR', 'Manual'
                FOREIGN KEY (meeting_id) REFERENCES meetings (id),
                FOREIGN KEY (student_nim) REFERENCES students (nim),
                UNIQUE(meeting_id, student_nim)
            )
            """)

            # 5. Quizzes Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                questions_json TEXT NOT NULL, -- JSON list of questions
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
            """)

            # 6. Quiz Submissions Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS quiz_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                student_nim TEXT NOT NULL,
                score REAL NOT NULL,
                answers_json TEXT NOT NULL, -- JSON dict {question_id: choice}
                submitted_at TEXT NOT NULL,
                FOREIGN KEY (quiz_id) REFERENCES quizzes (id),
                FOREIGN KEY (student_nim) REFERENCES students (nim),
                UNIQUE(quiz_id, student_nim)
            )
            """)

            # 7. Topic Mastery & Psychometrics Cache
            cur.execute("""
            CREATE TABLE IF NOT EXISTS topic_mastery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                meeting_id INTEGER NOT NULL,
                subtopic TEXT NOT NULL,
                difficulty_p REAL NOT NULL,
                discrimination_d REAL NOT NULL,
                status TEXT NOT NULL, -- 'Mastered', 'Need Review', 'Critical'
                anomaly_alert INTEGER DEFAULT 0,
                calculated_at TEXT NOT NULL,
                FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
            )
            """)

            # 8. Chat History Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL, -- 'user', 'assistant'
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """)

            conn.commit()

            # Seed Course if empty
            cur.execute("SELECT COUNT(*) FROM courses")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                INSERT INTO courses (id, name, code, class_code, prodi, semester, academic_year, sks)
                VALUES ('MPI-07TPLP003', 'Manajemen Proyek Informatika', 'TIF-701', '07TPLP003', 
                        'Teknik Informatika S1', 7, '2026/2027 Ganjil', 3)
                """)
                conn.commit()

            # Seed Students from CSV
            cur.execute("SELECT COUNT(*) FROM students")
            if cur.fetchone()[0] == 0 and os.path.exists(CSV_PATH):
                df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
                for _, row in df.iterrows():
                    nim = str(row.get("NIM", "")).strip()
                    nama = str(row.get("Nama", "")).strip()
                    if nim and nama:
                        cur.execute(
                            "INSERT OR IGNORE INTO students (nim, name, class_code) VALUES (?, ?, ?)",
                            (nim, nama, "07TPLP003")
                        )
                conn.commit()

            # Seed Meetings
            cur.execute("SELECT COUNT(*) FROM meetings")
            if cur.fetchone()[0] == 0:
                sample_meetings = [
                    (1, 1, "Pengantar Manajemen Proyek TI & Metodologi SDLC", "2026-09-08", "completed"),
                    (2, 2, "Project Charter, Scope Management & Stakeholder Analysis", "2026-09-15", "completed"),
                    (3, 3, "Work Breakdown Structure (WBS) & Dekomposisi Tugas", "2026-09-22", "completed"),
                    (4, 4, "Project Scheduling: Critical Path Method (CPM) & Gantt Chart", "2026-09-29", "completed"),
                    (5, 5, "Cost Estimation & Earned Value Analysis (EVA)", "2026-10-06", "active"),
                    (6, 6, "Manajemen Risiko Proyek & Mitigasi Risiko TI", "2026-10-13", "upcoming"),
                    (7, 7, "Quality Assurance Proyek & Agile/Scrum Framework", "2026-10-20", "upcoming"),
                    (8, 8, "Evaluasi Tengah Semester & Presentasi Milestone", "2026-10-27", "upcoming")
                ]
                cur.executemany(
                    "INSERT INTO meetings (id, meeting_no, topic, date_str, status) VALUES (?, ?, ?, ?, ?)",
                    sample_meetings
                )
                conn.commit()

            # Seed Historical Attendance & Quizzes if needed
            self._seed_sample_data(conn)
            conn.close()

    def _seed_sample_data(self, conn: sqlite3.Connection) -> None:
        """Seeds realistic historical attendance and quizzes for rich dashboard visualization."""
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM attendance")
        if cur.fetchone()[0] > 0:
            return  # Already seeded

        # Fetch all students
        cur.execute("SELECT nim, name FROM students ORDER BY name ASC")
        students = cur.fetchall()
        if not students:
            return

        # Seed attendance for meetings 1, 2, 3, 4, 5
        import random
        random.seed(42)  # Deterministic realistic mock data

        # For Meeting 1 to 4: completed attendance
        for m_id in [1, 2, 3, 4]:
            for idx, st in enumerate(students):
                nim = st["nim"]
                # 85-95% attendance rate
                is_hadir = random.random() < (0.92 if m_id != 3 else 0.82)
                status = "Hadir" if is_hadir else random.choice(["Belum Hadir", "Izin", "Sakit"])
                timestamp = f"08:{random.randint(1, 25):02d}:{random.randint(10, 59):02d}" if is_hadir else ""
                method = random.choice(["NIM Exact", "Nama Fuzzy", "Barcode/QR"]) if is_hadir else ""
                cur.execute(
                    "INSERT INTO attendance (meeting_id, student_nim, status, timestamp, method) VALUES (?, ?, ?, ?, ?)",
                    (m_id, nim, status, timestamp, method)
                )

        # For Active Meeting 5: Initial attendance (some marked Hadir, some Belum Hadir)
        for idx, st in enumerate(students):
            nim = st["nim"]
            # Suppose Aditya (our sample card) and first 6 students already tapped in
            if nim == "231011402760" or idx < 5:
                status = "Hadir"
                timestamp = f"08:{idx+5:02d}:14"
                method = "NIM Exact"
            else:
                status = "Belum Hadir"
                timestamp = ""
                method = ""
            cur.execute(
                "INSERT INTO attendance (meeting_id, student_nim, status, timestamp, method) VALUES (?, ?, ?, ?, ?)",
                (5, nim, status, timestamp, method)
            )

        # Seed Sample Quizzes for Meetings 1, 2, 3, 4
        # Meeting 1 Quiz
        q1_questions = [
            {
                "id": 1,
                "question": "Dokumen resmi awal yang mengesahkan keberadaan sebuah proyek dan memberi otoritas kepada Project Manager disebut?",
                "options": ["A. Work Breakdown Structure", "B. Project Charter", "C. Risk Register", "D. Gantt Chart"],
                "correct": "B",
                "subtopic": "Project Charter & Otorisasi",
                "explanation": "Project Charter memberikan wewenang resmi kepada manajer proyek untuk mengalokasikan sumber daya organisasi."
            },
            {
                "id": 2,
                "question": "Fase dalam Project Life Cycle yang menyerap anggaran dan sumber daya terbanyak adalah?",
                "options": ["A. Inisiasi", "B. Perencanaan", "C. Eksekusi", "D. Penutupan"],
                "correct": "C",
                "subtopic": "Siklus Hidup Proyek",
                "explanation": "Fase eksekusi adalah tahapan di mana hasil deliverables benar-benar dikerjakan, sehingga memakan biaya dan tenaga terbesar."
            },
            {
                "id": 3,
                "question": "Manakah komponen Triple Constraint klasik dalam manajemen proyek?",
                "options": ["A. Scope, Time, Cost", "B. Profit, People, Planet", "C. Hardware, Software, Network", "D. Strategy, Tactic, Operation"],
                "correct": "A",
                "subtopic": "Triple Constraint",
                "explanation": "Segitiga manajemen proyek terdiri dari Lingkup (Scope), Waktu (Time), dan Biaya (Cost)."
            }
        ]
        cur.execute(
            "INSERT INTO quizzes (meeting_id, title, topic, questions_json, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Quick Quiz Pertemuan 1", "Pengantar Manajemen Proyek TI", json.dumps(q1_questions), "2026-09-08 09:30:00", 0)
        )
        q1_id = cur.lastrowid

        # Meeting 3 Quiz (Contoh pertemuan yang mengalami anomali penurunan nilai / materi kritis WBS)
        q3_questions = [
            {
                "id": 1,
                "question": "Prinsip '100% Rule' dalam pembuatan Work Breakdown Structure (WBS) menyatakan bahwa?",
                "options": [
                    "A. Proyek harus selesai 100% tepat waktu",
                    "B. WBS harus mencakup 100% dari seluruh ruang lingkup pekerjaan proyek tanpa ada yang terlewat atau berlebih",
                    "C. Biaya proyek harus 100% teralokasi di awal",
                    "D. Seluruh anggota tim harus bekerja 100% waktu penuh"
                ],
                "correct": "B",
                "subtopic": "Aturan 100% WBS",
                "explanation": "100% Rule adalah aturan fundamental WBS yang memastikan seluruh deliverables terangkum secara lengkap dan mutually exclusive."
            },
            {
                "id": 2,
                "question": "Tingkat hierarki terendah dari WBS yang dapat diestimasi durasi dan biayanya disebut?",
                "options": ["A. Milestone", "B. Work Package", "C. Task List", "D. Deliverable Root"],
                "correct": "B",
                "subtopic": "Work Package Decomposition",
                "explanation": "Work Package adalah unit terkecil dalam WBS yang dapat dikelola, diestimasi, dan diawasi oleh satu PIC."
            },
            {
                "id": 3,
                "question": "Jika sebuah dekomposisi WBS berfokus pada urutan kronologis waktu pengerjaan dan bukan deliverables, kesalahan apa yang terjadi?",
                "options": [
                    "A. Scope Creep",
                    "B. Process-oriented WBS error",
                    "C. Critical path bias",
                    "D. Budget overrun"
                ],
                "correct": "B",
                "subtopic": "Prinsip Deliverable-Oriented",
                "explanation": "WBS harus berorientasi pada deliverables (hasil nyata), bukan urutan aktivitas/proses kerja semata."
            }
        ]
        cur.execute(
            "INSERT INTO quizzes (meeting_id, title, topic, questions_json, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (3, "Quick Quiz Pertemuan 3", "Work Breakdown Structure (WBS)", json.dumps(q3_questions), "2026-09-22 09:30:00", 0)
        )
        q3_id = cur.lastrowid

        # Meeting 4 Quiz (Critical Path Method)
        q4_questions = [
            {
                "id": 1,
                "question": "Jalur Kritis (Critical Path) dalam diagram jaringan proyek adalah?",
                "options": [
                    "A. Jalur aktivitas dengan risiko kegagalan teknis paling tinggi",
                    "B. Jalur terpanjang dari awal hingga akhir proyek yang menentukan durasi total proyek tercepat yang mungkin",
                    "C. Jalur aktivitas dengan biaya pengeluaran terbesar",
                    "D. Jalur yang memiliki total slack / float bernilai positif tertinggi"
                ],
                "correct": "B",
                "subtopic": "Definisi Critical Path",
                "explanation": "Critical Path adalah urutan aktivitas terpanjang dalam network diagram; penundaan aktivitas di jalur ini otomatis menunda tanggal selesai proyek."
            },
            {
                "id": 2,
                "question": "Aktivitas yang berada pada jalur kritis selalu memiliki nilai Float (Slack) sebesar?",
                "options": ["A. Negatif tak terhingga", "B. Tepat 0 (Nol)", "C. Lebih dari 5 hari", "D. Setengah dari durasi aktivitas"],
                "correct": "B",
                "subtopic": "Total Float pada Critical Path",
                "explanation": "Total Float pada jalur kritis bernilai nol karena tidak memiliki toleransi keterlambatan tanpa menunda proyek."
            },
            {
                "id": 3,
                "question": "Teknik kompresi jadwal dengan menambahkan sumber daya tambahan pada aktivitas jalur kritis disebut?",
                "options": ["A. Fast Tracking", "B. Crashing", "C. Leveling", "D. Buffering"],
                "correct": "B",
                "subtopic": "Schedule Compression",
                "explanation": "Crashing menambah resources (misal lembur/alat tambahan) untuk memperpendek durasi, biasanya menambah biaya."
            }
        ]
        cur.execute(
            "INSERT INTO quizzes (meeting_id, title, topic, questions_json, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (4, "Quick Quiz Pertemuan 4", "Project Scheduling & Critical Path Method", json.dumps(q4_questions), "2026-09-29 09:30:00", 0)
        )
        q4_id = cur.lastrowid

        # Seed submissions for Quizzes 1, 3, 4
        # We simulate student answers:
        for q_id, questions, avg_target in [
            (q1_id, q1_questions, 0.85), # P1: Good mastery (85%)
            (q3_id, q3_questions, 0.42), # P3: Low mastery / Anomaly alert (42%)
            (q4_id, q4_questions, 0.76)  # P4: Moderate mastery (76%)
        ]:
            for st_idx, st in enumerate(students):
                nim = st["nim"]
                answers = {}
                correct_count = 0
                for q in questions:
                    # student capability modifier
                    prob = avg_target
                    if st_idx < 10:  # Top students
                        prob = min(0.98, prob + 0.25)
                    elif st_idx > 24: # Struggling students
                        prob = max(0.15, prob - 0.25)
                    
                    is_correct = random.random() < prob
                    if is_correct:
                        chosen = q["correct"]
                        correct_count += 1
                    else:
                        wrong_opts = [o[0] for o in q["options"] if o[0] != q["correct"]]
                        chosen = random.choice(wrong_opts) if wrong_opts else "A"
                    answers[str(q["id"])] = chosen

                score = round((correct_count / len(questions)) * 100, 1)
                cur.execute(
                    "INSERT INTO quiz_submissions (quiz_id, student_nim, score, answers_json, submitted_at) VALUES (?, ?, ?, ?, ?)",
                    (q_id, nim, score, json.dumps(answers), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )

        conn.commit()

    # --- Data Retrieval Methods ---

    def get_course_info(self) -> Dict[str, Any]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM courses LIMIT 1")
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else {}

    def get_all_students(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT nim, name, class_code FROM students ORDER BY name ASC")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows

    def get_all_meetings(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM meetings ORDER BY meeting_no ASC")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows

    def get_active_meeting(self) -> Dict[str, Any]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM meetings WHERE status = 'active' LIMIT 1")
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT * FROM meetings ORDER BY meeting_no ASC LIMIT 1")
                row = cur.fetchone()
            conn.close()
            return dict(row) if row else {}

    def set_active_meeting(self, meeting_id: int) -> bool:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE meetings SET status = 'completed' WHERE status = 'active'")
            cur.execute("UPDATE meetings SET status = 'active' WHERE id = ?", (meeting_id,))
            conn.commit()
            conn.close()
            return True

    def get_meeting_attendance(self, meeting_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
            SELECT s.nim, s.name, s.class_code,
                   COALESCE(a.status, 'Belum Hadir') as status,
                   COALESCE(a.timestamp, '') as timestamp,
                   COALESCE(a.method, '') as method
            FROM students s
            LEFT JOIN attendance a ON s.nim = a.student_nim AND a.meeting_id = ?
            ORDER BY s.name ASC
            """, (meeting_id,))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows

    def record_attendance(
        self,
        meeting_id: int,
        student_nim: str,
        method: str = "NIM Exact",
        custom_timestamp: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Records or updates student attendance for a specific meeting.
        Implements duplicate prevention (FR-04).
        """
        clean_nim = str(student_nim).strip()
        timestamp = custom_timestamp or datetime.now().strftime("%H:%M:%S")

        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()

            # Check student exists
            cur.execute("SELECT nim, name, class_code FROM students WHERE nim = ?", (clean_nim,))
            st = cur.fetchone()
            if not st:
                conn.close()
                return False, "Data Mahasiswa Tidak Ditemukan", None

            student_data = dict(st)

            # Check existing attendance in this meeting
            cur.execute("SELECT status, timestamp, method FROM attendance WHERE meeting_id = ? AND student_nim = ?", (meeting_id, clean_nim))
            att = cur.fetchone()

            if att and att["status"] == "Hadir":
                conn.close()
                student_data["timestamp"] = att["timestamp"]
                student_data["method"] = att["method"]
                student_data["status"] = "Hadir"
                return False, "Sudah Melakukan Presensi", student_data

            # Insert or update
            cur.execute("""
            INSERT INTO attendance (meeting_id, student_nim, status, timestamp, method)
            VALUES (?, ?, 'Hadir', ?, ?)
            ON CONFLICT(meeting_id, student_nim) DO UPDATE SET
                status = 'Hadir',
                timestamp = excluded.timestamp,
                method = excluded.method
            """, (meeting_id, clean_nim, timestamp, method))
            conn.commit()
            conn.close()

            student_data["status"] = "Hadir"
            student_data["timestamp"] = timestamp
            student_data["method"] = method
            return True, "Presensi Berhasil", student_data

    def toggle_manual_attendance(self, meeting_id: int, student_nim: str, new_status: str) -> bool:
        clean_nim = str(student_nim).strip()
        timestamp = datetime.now().strftime("%H:%M:%S") if new_status == "Hadir" else ""
        method = "Manual" if new_status == "Hadir" else ""

        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO attendance (meeting_id, student_nim, status, timestamp, method)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id, student_nim) DO UPDATE SET
                status = excluded.status,
                timestamp = excluded.timestamp,
                method = excluded.method
            """, (meeting_id, clean_nim, new_status, timestamp, method))
            conn.commit()
            conn.close()
            return True

    def reset_student_attendance(self, meeting_id: int, student_nim: str) -> bool:
        """Resets attendance for a specific student in a meeting back to Belum Hadir."""
        clean_nim = str(student_nim).strip()
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO attendance (meeting_id, student_nim, status, timestamp, method)
            VALUES (?, ?, 'Belum Hadir', '', '')
            ON CONFLICT(meeting_id, student_nim) DO UPDATE SET
                status = 'Belum Hadir',
                timestamp = '',
                method = ''
            """, (meeting_id, clean_nim))
            conn.commit()
            conn.close()
            return True

    def reset_meeting_attendance(self, meeting_id: int) -> bool:
        """Resets all attendance records for a meeting back to Belum Hadir."""
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
            UPDATE attendance SET status = 'Belum Hadir', timestamp = '', method = ''
            WHERE meeting_id = ?
            """, (meeting_id,))
            conn.commit()
            conn.close()
            return True

    def get_all_quizzes(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
            SELECT q.*, m.meeting_no, m.topic as meeting_topic,
                   (SELECT COUNT(*) FROM quiz_submissions qs WHERE qs.quiz_id = q.id) as submission_count,
                   (SELECT AVG(score) FROM quiz_submissions qs WHERE qs.quiz_id = q.id) as avg_score
            FROM quizzes q
            JOIN meetings m ON q.meeting_id = m.id
            ORDER BY q.id DESC
            """)
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["questions"] = json.loads(d.get("questions_json", "[]"))
                d["avg_score"] = round(d["avg_score"], 1) if d.get("avg_score") is not None else 0.0
                rows.append(d)
            conn.close()
            return rows

    def get_quiz_by_id(self, quiz_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
            SELECT q.*, m.meeting_no, m.topic as meeting_topic
            FROM quizzes q
            JOIN meetings m ON q.meeting_id = m.id
            WHERE q.id = ?
            """, (quiz_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            d = dict(row)
            d["questions"] = json.loads(d.get("questions_json", "[]"))

            # Fetch submissions
            cur.execute("SELECT student_nim, score, answers_json, submitted_at FROM quiz_submissions WHERE quiz_id = ?", (quiz_id,))
            sub_rows = cur.fetchall()
            d["submissions"] = [
                {
                    "student_nim": sr["student_nim"],
                    "score": sr["score"],
                    "answers": json.loads(sr["answers_json"]),
                    "submitted_at": sr["submitted_at"]
                }
                for sr in sub_rows
            ]
            conn.close()
            return d

    def create_quiz(self, meeting_id: int, title: str, topic: str, questions: List[Dict[str, Any]]) -> int:
        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
            INSERT INTO quizzes (meeting_id, title, topic, questions_json, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """, (meeting_id, title, topic, json.dumps(questions), now_str))
            quiz_id = cur.lastrowid
            conn.commit()
            conn.close()
            return quiz_id

    def submit_quiz_answer(self, quiz_id: int, student_nim: str, answers: Dict[str, str]) -> Tuple[float, int, int]:
        """Scores and saves student quiz submission."""
        clean_nim = str(student_nim).strip()
        quiz = self.get_quiz_by_id(quiz_id)
        if not quiz:
            raise ValueError("Kuis tidak ditemukan.")

        questions = quiz["questions"]
        correct_count = 0
        total_q = len(questions)

        for q in questions:
            qid_str = str(q["id"])
            if answers.get(qid_str, "").strip().upper() == q["correct"].strip().upper():
                correct_count += 1

        score = round((correct_count / total_q) * 100, 1) if total_q > 0 else 0.0

        with self._lock:
            conn = self.get_connection()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
            INSERT INTO quiz_submissions (quiz_id, student_nim, score, answers_json, submitted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(quiz_id, student_nim) DO UPDATE SET
                score = excluded.score,
                answers_json = excluded.answers_json,
                submitted_at = excluded.submitted_at
            """, (quiz_id, clean_nim, score, json.dumps(answers), now_str))
            conn.commit()
            conn.close()

        return score, correct_count, total_q


# Global Singleton
db = DatabaseManager()
