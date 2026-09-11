from datetime import date, datetime, timezone


def utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import String, Text, Float, Boolean, Integer, Date, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="teacher")
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class School(Base):
    __tablename__ = "schools"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    academic_year: Mapped[str] = mapped_column(String(32), default="2026/27")
    default_language: Mapped[str] = mapped_column(String(12), default="en")
    pass_mark: Mapped[float] = mapped_column(Float, default=50.0)


class ClassRoom(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(80))
    grade_level: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="active")
    students = relationship("Student", cascade="all, delete-orphan", back_populates="classroom")


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    student_code: Mapped[str] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="active")
    classroom = relationship("ClassRoom", back_populates="students")


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")


class AssessmentType(Base):
    __tablename__ = "assessment_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(100))
    max_score: Mapped[float] = mapped_column(Float, default=100)
    weight: Mapped[float] = mapped_column(Float, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_type_id: Mapped[int] = mapped_column(ForeignKey("assessment_types.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    title: Mapped[str] = mapped_column(String(180))
    date: Mapped[date] = mapped_column(Date)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    grading_mode: Mapped[str] = mapped_column(String(12), default="manual", nullable=False)


class StudentScore(Base):
    __tablename__ = "student_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"))
    status: Mapped[str] = mapped_column(String(24), default="entered")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    teacher_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    __table_args__ = (UniqueConstraint("student_id", "assessment_id", name="uq_student_assessment"),)


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_student_attendance"),)


class Exam(Base):
    __tablename__ = "exams"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    title: Mapped[str] = mapped_column(String(180))
    total_marks: Mapped[float] = mapped_column(Float)
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("assessments.id"), nullable=True)
    answer_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    question_no: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    max_score: Mapped[float] = mapped_column(Float)
    topic: Mapped[str | None] = mapped_column(String(140), nullable=True)
    answer_type: Mapped[str] = mapped_column(String(40), default="short_answer")
    __table_args__ = (UniqueConstraint("exam_id", "question_no", name="uq_exam_question_no"),)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    batch_job_id: Mapped[int | None] = mapped_column(ForeignKey("scan_batch_jobs.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    detected_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    detected_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    identity_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    identity_status: Mapped[str] = mapped_column(String(30), default="unresolved")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class ScanBatchJob(Base):
    __tablename__ = "scan_batch_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    completed_files: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    auto_stored_files: Mapped[int] = mapped_column(Integer, default=0)
    review_required_files: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AIResult(Base):
    __tablename__ = "ai_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    suggested_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    mistake_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(140), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_teacher_review: Mapped[bool] = mapped_column(Boolean, default=True)
    teacher_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class Mistake(Base):
    __tablename__ = "mistakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    topic: Mapped[str] = mapped_column(String(140))
    mistake_type: Mapped[str] = mapped_column(String(140))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    last_seen: Mapped[date] = mapped_column(Date)


class TeacherComment(Base):
    __tablename__ = "teacher_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class SyncOperation(Base):
    __tablename__ = "sync_operations"
    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    route: Mapped[str] = mapped_column(String(120))
    method: Mapped[str] = mapped_column(String(12))
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
