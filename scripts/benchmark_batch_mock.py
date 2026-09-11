"""Synthetic 120-paper pipeline benchmark.

This deliberately mocks Gemini so the measurement isolates upload validation,
image preprocessing, persistence, queue orchestration, concurrency and result
aggregation. It is NOT a claim about real Gemini wall-clock latency or grading
accuracy; real-paper validation must be run with a representative teacher-
graded dataset and a real API key before school-wide deployment.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

DB = Path("benchmark_120.db")
DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///./benchmark_120.db"
os.environ["SECRET_KEY"] = "benchmark-secret-which-is-at-least-32-bytes-long"
os.environ["GEMINI_API_KEY"] = "benchmark-key"
os.environ["AI_BATCH_WORKERS"] = "6"

from fastapi.testclient import TestClient
from PIL import Image
from app import main as main_module
from app.schemas import AIGradingOutput


class FakeGemini:
    def __init__(self):
        self.enabled = True

    def analyze_answer_sheet(self, image_path, mime_type, questions, answer_key):
        return AIGradingOutput.model_validate({
            "identity": {
                "name_found": False,
                "detected_name": None,
                "detected_code": None,
                "confidence": 0.1,
                "evidence": "Synthetic benchmark",
            },
            "questions": [],
            "overall_feedback": "Synthetic benchmark",
        })


main_module.GeminiService = FakeGemini

with TestClient(main_module.app) as client:
    login = client.post("/api/auth/login", json={"email": "teacher@example.com", "password": "Teacher123!"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    cls = client.post("/api/classes", headers=headers, json={"name": "Benchmark 120", "grade_level": "10"}).json()
    subj = client.post("/api/subjects", headers=headers, json={"name": "Benchmark Subject"}).json()
    typ = client.post("/api/assessment-types", headers=headers, json={"name": "Benchmark Type", "max_score": 10, "weight": 100, "enabled": True, "sort_order": 1}).json()
    ass = client.post("/api/assessments", headers=headers, json={"assessment_type_id": typ["id"], "subject_id": subj["id"], "title": "Benchmark Assessment", "date": "2026-09-11", "class_id": cls["id"]}).json()
    exam = client.post("/api/exams", headers=headers, json={"class_id": cls["id"], "subject_id": subj["id"], "assessment_id": ass["id"], "title": "Benchmark Exam", "total_marks": 10, "answer_key": "Q1 benchmark"}).json()
    client.post("/api/questions", headers=headers, json={"exam_id": exam["id"], "question_no": 1, "question_text": "Benchmark", "max_score": 10, "topic": "Benchmark", "answer_type": "short_answer"})

    img = Path("benchmark_sheet.png")
    Image.new("RGB", (1000, 1400), "white").save(img)
    opened = [(img.name, img.open("rb")) for _ in range(120)]
    files = [("uploads", (name, fh, "image/png")) for name, fh in opened]
    start = time.perf_counter()
    try:
        response = client.post(f"/api/exams/{exam['id']}/scan-batch", headers=headers, files=files)
    finally:
        for _, fh in opened:
            fh.close()
    response.raise_for_status()
    job_id = response.json()["job_id"]
    deadline = time.perf_counter() + 60
    while time.perf_counter() < deadline:
        status = client.get(f"/api/scan-jobs/{job_id}", headers=headers).json()
        if status["completed_files"] >= 120:
            break
        time.sleep(0.1)
    elapsed = time.perf_counter() - start
    print({
        "total_files": status["total_files"],
        "completed_files": status["completed_files"],
        "succeeded_files": status["succeeded_files"],
        "failed_files": status["failed_files"],
        "status": status["status"],
        "elapsed_seconds": round(elapsed, 3),
        "papers_per_second": round(status["completed_files"] / elapsed, 2) if elapsed else None,
        "note": "Synthetic/mock Gemini benchmark; not real grading latency or accuracy.",
    })

img.unlink(missing_ok=True)
DB.unlink(missing_ok=True)
