from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class LoginIn(BaseModel):
    email: str
    password: str

class SignUpIn(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    password_confirm: str = Field(min_length=10, max_length=128)
    school_name: str = Field(min_length=2, max_length=160)

class UserOut(BaseModel):
    id: int; email: str; full_name: str; role: str
    model_config = ConfigDict(from_attributes=True)

class SchoolIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    academic_year: str = Field(min_length=1, max_length=32)
    default_language: str = Field(default="en", max_length=12)
    pass_mark: float = Field(default=50, ge=0, le=100)

class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    grade_level: str = Field(min_length=1, max_length=40)

class StudentIn(BaseModel):
    class_id: int
    student_code: str = Field(default="", max_length=40)
    full_name: str = Field(min_length=1, max_length=160)

class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

class AssessmentTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    max_score: float = Field(gt=0)
    weight: float = Field(ge=0, le=100)
    enabled: bool = True
    sort_order: int = 0

class AssessmentIn(BaseModel):
    assessment_type_id: int
    subject_id: int
    title: str = Field(min_length=1, max_length=180)
    date: date
    class_id: int | None = None
    grading_mode: Literal["manual", "ai"] = "manual"

class ScoreIn(BaseModel):
    student_id: int
    assessment_id: int
    status: Literal["entered","empty","zero","absent","excused","not_applicable"]
    score: float | None = Field(default=None, ge=0)
    teacher_note: str | None = None

class AttendanceIn(BaseModel):
    student_id: int
    date: date
    status: Literal["present","absent","late","excused"]

class ExamIn(BaseModel):
    class_id: int
    subject_id: int
    assessment_id: int | None = None
    title: str = Field(min_length=1, max_length=180)
    total_marks: float = Field(gt=0)
    answer_key: str | None = None

class QuestionIn(BaseModel):
    exam_id: int
    question_no: int = Field(gt=0)
    question_text: str = Field(min_length=1)
    max_score: float = Field(gt=0)
    topic: str | None = None
    answer_type: str = "short_answer"

class AssignStudentIn(BaseModel):
    student_id: int

class ReviewIn(BaseModel):
    teacher_score: float = Field(ge=0)
    reason: str | None = None
    action: Literal["accept","edit","reject","recheck"]

class AIStudentIdentity(BaseModel):
    name_found: bool
    detected_name: str | None = None
    detected_code: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: str

class AIQuestionResult(BaseModel):
    question_id: int
    student_answer: str
    expected_answer: str | None = None
    score: float = Field(ge=0)
    maximum_score: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    reason: str
    mistake_type: str
    topic: str
    subtopic: str
    feedback: str
    needs_teacher_review: bool

class AIGradingOutput(BaseModel):
    identity: AIStudentIdentity
    questions: list[AIQuestionResult]
    overall_feedback: str


class SyncOperationIn(BaseModel):
    operation_id: str = Field(min_length=8, max_length=80)
    method: Literal["POST", "PATCH"]
    path: str = Field(min_length=1, max_length=180)
    body: dict

class SyncBatchIn(BaseModel):
    operations: list[SyncOperationIn] = Field(default_factory=list, max_length=100)
