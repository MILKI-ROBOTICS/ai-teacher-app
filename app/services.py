from datetime import date
from pathlib import Path
import difflib
import json
import re
import uuid

from PIL import Image, ImageOps, ImageFilter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import StudentScore, AssessmentType, Student, Assessment, Attendance, Mistake, AuditLog

VALID_UPLOADS = {"image/jpeg", "image/png", "image/webp"}
NON_COUNTING_STATUSES = {"empty", "absent", "excused", "not_applicable"}


def roster_metrics(db: Session, student_ids: list[int]) -> dict[int, dict[str, float]]:
    if not student_ids:
        return {}
    score_rows = db.execute(
        select(StudentScore.student_id, StudentScore.status, StudentScore.score, AssessmentType.max_score, AssessmentType.weight)
        .join(Assessment, StudentScore.assessment_id == Assessment.id)
        .join(AssessmentType, Assessment.assessment_type_id == AssessmentType.id)
        .where(StudentScore.student_id.in_(student_ids), AssessmentType.enabled == True, AssessmentType.weight > 0)
    ).all()
    avg_acc: dict[int, list[float]] = {}
    for sid, status, score, max_score, weight in score_rows:
        if status in NON_COUNTING_STATUSES or score is None or max_score <= 0:
            continue
        avg_acc.setdefault(sid, [0.0, 0.0])
        avg_acc[sid][0] += (float(score) / float(max_score)) * float(weight)
        avg_acc[sid][1] += float(weight)
    attendance_rows = db.execute(
        select(Attendance.student_id, Attendance.status)
        .where(Attendance.student_id.in_(student_ids))
    ).all()
    att_acc: dict[int, list[int]] = {}
    for sid, status in attendance_rows:
        counts = att_acc.setdefault(sid, [0, 0])
        counts[0] += 1
        counts[1] += 1 if status == 'present' else 0
    out = {}
    for sid in student_ids:
        total_weight = avg_acc.get(sid, [0.0, 0.0])[1]
        avg = (avg_acc[sid][0] / total_weight * 100) if total_weight else 0.0
        total, present = att_acc.get(sid, [0, 0])
        out[sid] = {"average": round(avg, 2), "attendance": round(present / total * 100, 1) if total else 0.0}
    return out


def recalc_student(db: Session, student_id: int) -> float:
    rows = db.execute(
        select(StudentScore, Assessment, AssessmentType)
        .join(Assessment, StudentScore.assessment_id == Assessment.id)
        .join(AssessmentType, Assessment.assessment_type_id == AssessmentType.id)
        .where(StudentScore.student_id == student_id, AssessmentType.enabled == True, AssessmentType.weight > 0)
    ).all()
    valid = [
        (score, at) for score, _, at in rows
        if score.status not in NON_COUNTING_STATUSES and score.score is not None and at.max_score > 0
    ]
    if not valid:
        return 0.0
    total_weight = sum(float(at.weight) for _, at in valid)
    weighted = sum((float(score.score) / float(at.max_score)) * float(at.weight) for score, at in valid)
    return round(weighted / total_weight * 100, 2) if total_weight else 0.0


def class_rankings(db: Session, class_id: int):
    students = db.scalars(select(Student).where(Student.class_id == class_id, Student.status == "active")).all()
    metrics = roster_metrics(db, [s.id for s in students])
    values = sorted(((s, metrics.get(s.id, {}).get("average", 0.0)) for s in students), key=lambda x: (-x[1], normalize_person_name(x[0].full_name), x[0].id))
    output = []
    last_score = None
    rank = 0
    for position, (student, score) in enumerate(values, 1):
        if score != last_score:
            rank = position
            last_score = score
        output.append({"student_id": student.id, "name": student.full_name, "average": score, "rank": rank})
    return output


def attendance_summary(db: Session, student_id: int):
    rows = db.scalars(select(Attendance).where(Attendance.student_id == student_id)).all()
    counts = {key: sum(1 for row in rows if row.status == key) for key in ("present", "absent", "late", "excused")}
    total = len(rows)
    percent = round(counts["present"] / total * 100, 1) if total else 0.0
    return {**counts, "attendance_percent": percent, "total": total}


def record_mistake(db: Session, student_id: int, topic: str | None, mistake_type: str | None):
    normalized = (mistake_type or "").strip()
    if not normalized or normalized.lower() in {"none", "correct", "n/a", ""}:
        return
    top = (topic or "Unmapped").strip() or "Unmapped"
    existing = db.scalar(
        select(Mistake).where(
            Mistake.student_id == student_id,
            Mistake.topic == top,
            Mistake.mistake_type == normalized,
        )
    )
    if existing:
        existing.occurrence_count += 1
        existing.last_seen = date.today()
    else:
        db.add(Mistake(student_id=student_id, topic=top, mistake_type=normalized, occurrence_count=1, last_seen=date.today()))


def audit(db: Session, user_id: int | None, entity: str, entity_id: int | None, action: str, old=None, new=None, reason=None):
    db.add(
        AuditLog(
            user_id=user_id,
            entity=entity,
            entity_id=entity_id,
            action=action,
            old_value=json.dumps(old, ensure_ascii=False, default=str) if old is not None else None,
            new_value=json.dumps(new, ensure_ascii=False, default=str) if new is not None else None,
            reason=reason,
        )
    )


def normalize_person_name(value: str | None) -> str:
    value = (value or "").casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def renumber_class_students(db: Session, class_id: int) -> list[Student]:
    students = db.scalars(
        select(Student).where(Student.class_id == class_id, Student.status == "active")
    ).all()
    students = sorted(students, key=lambda s: (normalize_person_name(s.full_name), s.id))
    for number, student in enumerate(students, start=1):
        student.student_code = str(number)
    return students


def match_detected_student(db: Session, class_id: int, detected_name: str | None, detected_code: str | None):
    students = db.scalars(select(Student).where(Student.class_id == class_id, Student.status == "active")).all()
    target = normalize_person_name(detected_name)
    code = (detected_code or "").strip().casefold()
    # Names are primary identity because sequential class numbers can change when the roster is edited.
    if target:
        scored = []
        for student in students:
            candidate = normalize_person_name(student.full_name)
            score = difflib.SequenceMatcher(None, target, candidate).ratio()
            scored.append((score, student))
        scored.sort(key=lambda x: (-x[0], x[1].full_name.casefold(), x[1].id))
        if scored:
            best_score, best_student = scored[0]
            second = scored[1][0] if len(scored) > 1 else 0.0
            if best_score >= 0.93 and best_score - second >= 0.04:
                return best_student, best_score, "name_exactish", scored[:5]
            if best_score >= 0.78 and best_score - second >= 0.10:
                return best_student, best_score, "name_fuzzy", scored[:5]
            # Exact normalized name with a differing sequential number is still strong evidence.
            if best_score == 1.0:
                return best_student, best_score, "name_exact", scored[:5]
            return None, best_score, "ambiguous", scored[:5]
    if code:
        exact = [s for s in students if s.student_code.casefold().strip() == code]
        if len(exact) == 1:
            return exact[0], 1.0, "code_exact", [(1.0, exact[0])]
    return None, 0.0, "unmatched", []


def validate_image_and_prepare(src: Path, mime_type: str | None = None) -> dict:
    if mime_type not in VALID_UPLOADS:
        raise ValueError("Upload a JPG, PNG, or WEBP image")
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        width, height = img.size
        gray = ImageOps.grayscale(img)
        small = gray.resize((min(500, max(1, width)), min(500, max(1, height))))
        hist = small.histogram()
        pixels = max(1, small.size[0] * small.size[1])
        brightness = float(sum(index * count for index, count in enumerate(hist)) / pixels)
        edges = small.filter(ImageFilter.FIND_EDGES)
        edge_hist = edges.histogram()
        edge_signal = float(sum(index * count for index, count in enumerate(edge_hist)) / pixels)
        quality = {
            "width": width,
            "height": height,
            "aspect_ratio": round(width / height, 3) if height else 0,
            "mean_brightness": round(brightness, 1),
            "edge_signal": round(edge_signal, 1),
            "readability_hint": "good" if width >= 1000 and 35 <= brightness <= 225 else "check_image",
        }
        out = Path(settings.upload_dir) / f"processed_{uuid.uuid4().hex}.jpg"
        img.thumbnail((3000, 3000))
        img.save(out, "JPEG", quality=90, optimize=True)
        return {"processed_path": str(out), "quality": quality}
