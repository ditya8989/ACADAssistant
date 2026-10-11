"""
Psychometrics & Data Mining Engine for ACAD Assistant.
Implements Fitur 3 PRD:
1. Item Difficulty Index (P = B / N)
2. Discrimination Index (D = (B_upper - B_lower) / (N / 2))
3. Anomaly Detection (Extreme class drop / Alert < 50%)
4. Student Risk Clustering (K-Means into 3 segments: Mastered, Borderline, At-Risk)
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from database.db_manager import db


class PsychometricsEngine:
    """Calculates educational item metrics and student risk clustering."""

    @staticmethod
    def analyze_quiz(quiz_id: int) -> Dict[str, Any]:
        """
        Calculates Difficulty Index (P) and Discrimination Index (D) for each question in a quiz.
        Returns item-level statistics and identifies critical subtopics.
        """
        quiz = db.get_quiz_by_id(quiz_id)
        if not quiz:
            return {"error": "Kuis tidak ditemukan"}

        questions = quiz.get("questions", [])
        submissions = quiz.get("submissions", [])
        total_respondents = len(submissions)

        if total_respondents == 0:
            return {
                "quiz_id": quiz_id,
                "title": quiz.get("title"),
                "total_respondents": 0,
                "items": [],
                "critical_subtopics": [],
                "class_average": 0.0,
                "anomaly_alert": False
            }

        # Sort submissions by score descending to determine Upper and Lower groups
        sorted_subs = sorted(submissions, key=lambda s: s["score"], reverse=True)
        half_n = max(1, total_respondents // 2)
        upper_group = sorted_subs[:half_n]
        lower_group = sorted_subs[-half_n:]

        items_analysis = []
        critical_subtopics = []

        for q in questions:
            qid_str = str(q["id"])
            correct_key = q["correct"].strip().upper()
            subtopic = q.get("subtopic", f"Butir {qid_str}")

            # Count total correct answers B
            correct_b = sum(
                1 for s in submissions
                if s.get("answers", {}).get(qid_str, "").strip().upper() == correct_key
            )

            # Difficulty Index P = B / N
            p_value = round(correct_b / total_respondents, 3)

            # Discrimination Index D
            # Correct in upper group
            b_upper = sum(
                1 for s in upper_group
                if s.get("answers", {}).get(qid_str, "").strip().upper() == correct_key
            )
            # Correct in lower group
            b_lower = sum(
                1 for s in lower_group
                if s.get("answers", {}).get(qid_str, "").strip().upper() == correct_key
            )

            d_value = round((b_upper - b_lower) / half_n, 3)

            # PRD Section 3: Nilai P < 0.4 ditandai sebagai sub-topik kritis / belum dikuasai kelas
            is_critical = p_value < 0.40
            if is_critical:
                critical_subtopics.append({
                    "subtopic": subtopic,
                    "difficulty_p": p_value,
                    "discrimination_d": d_value,
                    "question_id": q["id"]
                })

            # Status interpretation
            if p_value < 0.40:
                difficulty_label = "Sukar (Kritis)"
            elif p_value <= 0.70:
                difficulty_label = "Sedang (Ideal)"
            else:
                difficulty_label = "Mudah"

            if d_value >= 0.40:
                discrimination_label = "Sangat Baik"
            elif d_value >= 0.30:
                discrimination_label = "Baik"
            elif d_value >= 0.20:
                discrimination_label = "Cukup"
            elif d_value >= 0:
                discrimination_label = "Buruk / Perlu Revisi"
            else:
                discrimination_label = "Kunci/Soal Berindikasi Anomali"

            items_analysis.append({
                "question_id": q["id"],
                "question_text": q["question"],
                "subtopic": subtopic,
                "correct_key": correct_key,
                "total_respondents": total_respondents,
                "correct_count": correct_b,
                "difficulty_p": p_value,
                "difficulty_label": difficulty_label,
                "discrimination_d": d_value,
                "discrimination_label": discrimination_label,
                "is_critical": is_critical
            })

        class_average = round(sum(s["score"] for s in submissions) / total_respondents, 1)

        # Anomaly Detection: Rata-rata di bawah 50% memicu alert otomatis
        anomaly_alert = class_average < 50.0

        return {
            "quiz_id": quiz_id,
            "title": quiz.get("title"),
            "meeting_no": quiz.get("meeting_no"),
            "meeting_topic": quiz.get("meeting_topic"),
            "total_respondents": total_respondents,
            "class_average": class_average,
            "items": items_analysis,
            "critical_subtopics": critical_subtopics,
            "anomaly_alert": anomaly_alert
        }

    @staticmethod
    def get_student_risk_clusters() -> Dict[str, Any]:
        """
        Segments all 32 students into 3 clusters using K-Means:
        - Segment 1: Mastered
        - Segment 2: Borderline
        - Segment 3: At-Risk
        Features used: Attendance Rate (%), Quiz Average Score (0-100).
        """
        students = db.get_all_students()
        meetings = db.get_all_meetings()
        quizzes = db.get_all_quizzes()
        completed_meetings = [m for m in meetings if m["status"] in ["completed", "active"]]
        total_meetings_evaluated = max(1, len(completed_meetings))

        student_data = []

        for st in students:
            nim = st["nim"]
            name = st["name"]

            # Calculate Attendance Rate
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE student_nim = ? AND status = 'Hadir'
            """, (nim,))
            hadir_count = cur.fetchone()[0]

            att_rate = round((hadir_count / total_meetings_evaluated) * 100, 1)

            # Calculate Quiz Average
            cur.execute("""
            SELECT AVG(score) FROM quiz_submissions
            WHERE student_nim = ?
            """, (nim,))
            avg_quiz_row = cur.fetchone()[0]
            conn.close()

            quiz_avg = round(float(avg_quiz_row), 1) if avg_quiz_row is not None else 0.0

            # Combined Composite Score
            composite = round((0.4 * att_rate) + (0.6 * quiz_avg), 1)

            student_data.append({
                "nim": nim,
                "name": name,
                "attendance_rate": att_rate,
                "quiz_avg": quiz_avg,
                "composite": composite,
                "hadir_count": hadir_count,
                "total_meetings": total_meetings_evaluated
            })

        if not student_data:
            return {"clusters": {}, "summary": {}}

        # Prepare feature matrix for K-Means: [attendance_rate, quiz_avg]
        X = np.array([[s["attendance_rate"], s["quiz_avg"]] for s in student_data])

        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Run K-Means with k=3
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Map cluster numeric labels to domain semantics:
        # Determine cluster rankings based on mean composite score of cluster
        cluster_composite_means = {}
        for c_id in range(3):
            scores = [student_data[i]["composite"] for i in range(len(student_data)) if labels[i] == c_id]
            cluster_composite_means[c_id] = np.mean(scores) if scores else 0.0

        # Sort clusters by composite score: Highest -> Mastered, Middle -> Borderline, Lowest -> At-Risk
        sorted_clusters = sorted(cluster_composite_means.keys(), key=lambda k: cluster_composite_means[k], reverse=True)
        label_map = {
            sorted_clusters[0]: "Mastered",
            sorted_clusters[1]: "Borderline",
            sorted_clusters[2]: "At-Risk"
        }

        # Assign labels to students
        for i, s in enumerate(student_data):
            raw_cluster = labels[i]
            assigned_label = label_map[raw_cluster]
            s["cluster"] = assigned_label

        # Sort students within each cluster
        mastered_list = [s for s in student_data if s["cluster"] == "Mastered"]
        borderline_list = [s for s in student_data if s["cluster"] == "Borderline"]
        at_risk_list = [s for s in student_data if s["cluster"] == "At-Risk"]

        return {
            "total_students": len(student_data),
            "counts": {
                "mastered": len(mastered_list),
                "borderline": len(borderline_list),
                "at_risk": len(at_risk_list)
            },
            "clusters": {
                "Mastered": mastered_list,
                "Borderline": borderline_list,
                "At-Risk": at_risk_list
            },
            "students": student_data
        }

    @staticmethod
    def get_dashboard_summary() -> Dict[str, Any]:
        """
        Compiles all metrics for Fitur 1 (Home Beranda Dashboard):
        - KPI Cards
        - Attendance Trend line chart data
        - Topic Mastery / Quiz performance heatmap/bar data
        - Early Alert Banners
        """
        course = db.get_course_info()
        meetings = db.get_all_meetings()
        active_meeting = db.get_active_meeting()
        students = db.get_all_students()

        # 1. Active / Current Week Attendance
        act_id = active_meeting.get("id", 1)
        active_att = db.get_meeting_attendance(act_id)
        hadir_count = sum(1 for a in active_att if a["status"] == "Hadir")
        total_students = len(students)
        weekly_att_rate = round((hadir_count / total_students) * 100, 1) if total_students > 0 else 0.0

        # 2. Risk Clustering
        clustering_result = PsychometricsEngine.get_student_risk_clusters()
        at_risk_count = clustering_result["counts"]["at_risk"]

        # 3. Attendance Trend across meetings
        attendance_trend = []
        conn = db.get_connection()
        cur = conn.cursor()
        for m in meetings:
            cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE meeting_id = ? AND status = 'Hadir'
            """, (m["id"],))
            h = cur.fetchone()[0]
            rate = round((h / total_students) * 100, 1) if total_students > 0 else 0.0
            attendance_trend.append({
                "meeting_no": m["meeting_no"],
                "meeting_id": m["id"],
                "topic": m["topic"],
                "hadir_count": h,
                "total_students": total_students,
                "rate": rate,
                "status": m["status"]
            })
        conn.close()

        # 4. Quizzes & Topic Mastery
        quizzes = db.get_all_quizzes()
        active_quiz_count = sum(1 for q in quizzes if q.get("is_active", 0) == 1)

        quiz_metrics = []
        all_critical_subtopics = []
        early_alert = False
        alert_message = ""

        for q in quizzes:
            analysis = PsychometricsEngine.analyze_quiz(q["id"])
            if analysis.get("critical_subtopics"):
                all_critical_subtopics.extend(analysis["critical_subtopics"])
            if analysis.get("anomaly_alert"):
                early_alert = True
                alert_message = f"Peringatan Dini: Rata-rata pemahaman Pertemuan {analysis.get('meeting_no')} ({analysis.get('meeting_topic')}) berada di bawah 50% ({analysis.get('class_average')}%). Disarankan sesi review/remedial!"

            quiz_metrics.append({
                "quiz_id": q["id"],
                "meeting_no": q.get("meeting_no"),
                "topic": q.get("meeting_topic"),
                "class_average": analysis.get("class_average", 0.0),
                "total_respondents": analysis.get("total_respondents", 0),
                "critical_count": len(analysis.get("critical_subtopics", []))
            })

        return {
            "course": course,
            "kpi": {
                "weekly_attendance_rate": weekly_att_rate,
                "active_meeting_no": active_meeting.get("meeting_no"),
                "active_meeting_topic": active_meeting.get("topic"),
                "hadir_count": hadir_count,
                "total_students": total_students,
                "active_quiz_count": len(quizzes),
                "need_review_topics_count": len(all_critical_subtopics),
                "at_risk_students_count": at_risk_count
            },
            "early_alert": {
                "triggered": early_alert,
                "message": alert_message
            },
            "attendance_trend": attendance_trend,
            "quiz_performance": quiz_metrics,
            "critical_subtopics": all_critical_subtopics,
            "cluster_summary": clustering_result["counts"]
        }
