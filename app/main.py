from datetime import date, datetime, timezone
from pathlib import Path
import csv
import io
import json
import os
import re
import secrets
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from .db import Base, engine, get_db, SessionLocal
from .models import *
from .schemas import *
from .security import hash_password, verify_password, create_token, decode_token
from .services import (
    recalc_student, class_rankings, attendance_summary, record_mistake, audit,
    validate_image_and_prepare, match_detected_student, renumber_class_students, roster_metrics,
)
from .ai_service import GeminiService, GeminiUnavailable
from .config import settings

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        school = db.scalar(select(School).order_by(School.id))
        if not school:
            school = School(name=settings.school_name, academic_year=settings.academic_year, default_language="en")
            db.add(school); db.flush()
        demo = db.scalar(select(User).where(User.email == settings.demo_teacher_email))
        if settings.app_env.lower() != "production" and getattr(settings, "allow_demo_account", True):
            if not demo:
                db.add(User(email=settings.demo_teacher_email, full_name=settings.demo_teacher_name, password_hash=hash_password(settings.demo_teacher_password), role="teacher", school_id=school.id))
            elif demo.school_id is None:
                demo.school_id = school.id
        elif demo and demo.school_id is None:
            demo.school_id = school.id
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="AI Teacher Intelligence", version="6.0.0", lifespan=lifespan)
allowed_origins = [x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/") and request.url.path not in {"/api/auth/login", "/api/auth/signup"}:
        if not request.headers.get("Authorization"):
            cookie = request.cookies.get("ati_csrf")
            header = request.headers.get("X-CSRF-Token")
            if not cookie or not header or not secrets.compare_digest(cookie, header):
                return JSONResponse(status_code=403, content={"detail": "CSRF validation failed. Refresh the page and try again."})
    return await call_next(request)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if settings.app_env.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
app.mount("/static", StaticFiles(directory="app/static"), name="static")
bearer = HTTPBearer(auto_error=False)
login_attempts = defaultdict(list)
signup_attempts = defaultdict(list)

def _csrf_token():
    return secrets.token_urlsafe(32)

def _set_auth_cookies(response: Response, token: str, request: Request | None = None):
    secure = settings.session_cookie_secure or settings.app_env.lower() == "production"
    mobile_origin = bool(request and (request.headers.get("origin", "").startswith("capacitor://") or request.headers.get("x-ati-mobile") == "1"))
    samesite = "none" if mobile_origin and secure else settings.session_cookie_samesite
    response.set_cookie(settings.session_cookie_name, token, httponly=True, secure=secure, samesite=samesite, path="/")
    csrf = _csrf_token()
    response.set_cookie("ati_csrf", csrf, httponly=False, secure=secure, samesite=samesite, path="/")

def _clear_auth_cookies(response: Response):
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("ati_csrf", path="/")

def _client_key(request):
    return request.client.host if request.client else "unknown"

def _check_login_rate(request):
    now = time.time(); key=_client_key(request); items=[t for t in login_attempts[key] if now-t < settings.login_window_seconds]
    login_attempts[key]=items
    if len(items) >= settings.max_login_attempts:
        raise HTTPException(429, "Too many failed sign-in attempts. Please wait a few minutes and try again.")

def _record_login_failure(request):
    login_attempts[_client_key(request)].append(time.time())


@app.get("/")
def home():
    return FileResponse("app/templates/index.html")

@app.get("/site.webmanifest")
def site_manifest():
    return FileResponse("app/static/manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": app.version, "gemini_configured": bool(settings.gemini_api_key), "model": settings.gemini_model, "batch_max_files": settings.max_batch_files}


def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    token = creds.credentials if creds else request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(401, "Authentication required")
    try:
        uid, token_version = decode_token(token)
    except Exception as exc:
        raise HTTPException(401, "Invalid or expired session") from exc
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User not found")
    if int(getattr(user, "session_version", 1)) != int(token_version):
        raise HTTPException(401, "Session expired. Please sign in again.")
    return user


def protected(user=Depends(current_user)):
    return user


def school_or_404(db: Session, user):
    if not getattr(user, "school_id", None):
        raise HTTPException(403, "Your account is not linked to a workspace")
    school = db.get(School, user.school_id)
    if not school:
        raise HTTPException(500, "Workspace is not initialized")
    return school


@app.post("/api/auth/signup")
def signup(data: SignUpIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not settings.signup_enabled:
        raise HTTPException(403, "New account registration is currently disabled")
    now = time.time(); key = _client_key(request)
    signup_attempts[key] = [t for t in signup_attempts[key] if now - t < 3600]
    if len(signup_attempts[key]) >= 8:
        raise HTTPException(429, "Too many registration attempts. Please try again later.")
    email = data.email.lower().strip()
    signup_attempts[key].append(now)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Enter a valid email address")
    if data.password != data.password_confirm:
        raise HTTPException(400, "Passwords do not match")
    if not re.search(r"[A-Za-z]", data.password) or not re.search(r"\d", data.password):
        raise HTTPException(400, "Password must contain at least one letter and one number")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "An account with this email already exists")
    school = School(name=data.school_name.strip(), academic_year=settings.academic_year, default_language="en")
    db.add(school); db.flush()
    user = User(email=email, full_name=data.full_name.strip(), password_hash=hash_password(data.password), role="teacher", school_id=school.id)
    db.add(user); db.flush()
    audit(db, user.id, "user", user.id, "signup", new={"email": user.email, "school_id": school.id})
    db.commit()
    token = create_token(user.id, user.session_version)
    _set_auth_cookies(response, token, request)
    return {"user": UserOut.model_validate(user).model_dump(), "school": {"id": school.id, "name": school.name}, "message": "Account created successfully"}

@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _check_login_rate(request)
    user = db.scalar(select(User).where(User.email == data.email.lower().strip()))
    if not user or not verify_password(data.password, user.password_hash):
        _record_login_failure(request)
        raise HTTPException(401, "Invalid email or password")
    if not user.school_id:
        raise HTTPException(403, "Your account is not linked to a workspace")
    login_attempts.pop(_client_key(request), None)
    token = create_token(user.id, user.session_version)
    _set_auth_cookies(response, token, request)
    return {"access_token": token, "user": UserOut.model_validate(user).model_dump()}

@app.post("/api/auth/logout")
def logout(response: Response, db: Session = Depends(get_db), user=Depends(protected)):
    user.session_version = int(getattr(user, "session_version", 1)) + 1
    db.commit()
    _clear_auth_cookies(response)
    return {"ok": True}

@app.post("/api/auth/change-password")
def change_password(data: dict, response: Response, db: Session = Depends(get_db), user=Depends(protected)):
    current = str(data.get("current_password") or "")
    new = str(data.get("new_password") or "")
    if len(new) < 10 or not re.search(r"[A-Za-z]", new) or not re.search(r"\d", new):
        raise HTTPException(400, "New password must be at least 10 characters and contain a letter and number")
    if not verify_password(current, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(new)
    user.session_version = int(getattr(user, "session_version", 1)) + 1
    audit(db, user.id, "user", user.id, "change_password")
    db.commit()
    _clear_auth_cookies(response)
    return {"ok": True, "message": "Password changed. Please sign in again."}

@app.get("/api/me")
def me(user=Depends(protected)):
    return UserOut.model_validate(user)


@app.get("/api/school")
def get_school(db: Session = Depends(get_db), user=Depends(protected)):
    s = school_or_404(db, user)
    return {"id": s.id, "name": s.name, "academic_year": s.academic_year, "default_language": s.default_language, "pass_mark": s.pass_mark}


@app.patch("/api/school")
def update_school(data: SchoolIn, db: Session = Depends(get_db), user=Depends(protected)):
    s = school_or_404(db, user)
    old = {"name": s.name, "academic_year": s.academic_year, "default_language": s.default_language, "pass_mark": s.pass_mark}
    for key, value in data.model_dump().items():
        setattr(s, key, value)
    audit(db, user.id, "school", s.id, "update", old=old, new=data.model_dump())
    db.commit()
    return {"id": s.id, **data.model_dump()}


@app.get("/api/classes")
def classes(db: Session = Depends(get_db), user=Depends(protected)):
    return [
        {"id": c.id, "name": c.name, "grade_level": c.grade_level, "status": c.status,
         "student_count": db.scalar(select(func.count(Student.id)).where(Student.class_id == c.id, Student.status == "active")) or 0}
        for c in db.scalars(select(ClassRoom).where(ClassRoom.status == "active", ClassRoom.school_id == user.school_id).order_by(ClassRoom.name)).all()
    ]


@app.post("/api/classes")
def create_class(data: ClassIn, db: Session = Depends(get_db), user=Depends(protected)):
    school = school_or_404(db, user)
    name = data.name.strip()
    grade = data.grade_level.strip()
    duplicate = db.scalar(select(ClassRoom).where(ClassRoom.school_id == school.id, func.lower(ClassRoom.name) == name.lower(), ClassRoom.status == "active"))
    if duplicate:
        raise HTTPException(409, "That class already exists")
    obj = ClassRoom(school_id=school.id, name=name, grade_level=grade)
    db.add(obj)
    db.flush()
    audit(db, user.id, "class", obj.id, "create", new=data.model_dump())
    db.commit()
    return {"id": obj.id, "name": obj.name, "grade_level": obj.grade_level, "student_count": 0}


@app.patch("/api/classes/{class_id}")
def update_class(class_id: int, data: ClassIn, db: Session = Depends(get_db), user=Depends(protected)):
    obj = db.get(ClassRoom, class_id)
    if not obj or obj.school_id != user.school_id:
        raise HTTPException(404, "Class not found")
    old = {"name": obj.name, "grade_level": obj.grade_level}
    obj.name, obj.grade_level = data.name.strip(), data.grade_level.strip()
    audit(db, user.id, "class", obj.id, "update", old=old, new=data.model_dump())
    db.commit()
    return {"id": obj.id, "name": obj.name, "grade_level": obj.grade_level}


@app.post("/api/classes/{class_id}/archive")
def archive_class(class_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    obj = db.get(ClassRoom, class_id)
    if not obj or obj.school_id != user.school_id:
        raise HTTPException(404, "Class not found")
    old = obj.status
    obj.status = "archived"
    audit(db, user.id, "class", obj.id, "archive", old={"status": old}, new={"status": obj.status})
    db.commit()
    return {"ok": True}


@app.get("/api/students")
def students(class_id: int | None = None, q: str = "", include_archived: bool = False, limit: int = Query(1000, ge=1, le=5000), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(protected)):
    stmt = select(Student).join(ClassRoom, Student.class_id == ClassRoom.id)
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    stmt = stmt.where(ClassRoom.school_id == user.school_id)
    if not include_archived:
        stmt = stmt.where(Student.status == "active")
    if q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where((Student.full_name.ilike(pattern)) | (Student.student_code.ilike(pattern)))
    rows = db.scalars(stmt.order_by(Student.full_name, Student.id).offset(offset).limit(limit)).all()
    metrics = roster_metrics(db, [s.id for s in rows])
    return [
        {"id": s.id, "class_id": s.class_id, "student_code": s.student_code, "full_name": s.full_name,
         "status": s.status, "average": metrics.get(s.id, {}).get("average", 0), "attendance": metrics.get(s.id, {}).get("attendance", 0)}
        for s in rows
    ]


@app.post("/api/students")
def create_student(data: StudentIn, db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, data.class_id)
    if not classroom or classroom.status != "active" or classroom.school_id != user.school_id:
        raise HTTPException(404, "Active class not found")
    name = data.full_name.strip()
    duplicate = db.scalar(
        select(Student).where(
            Student.class_id == data.class_id,
            func.lower(Student.full_name) == name.lower(),
            Student.status == "active",
        )
    )
    if duplicate:
        raise HTTPException(409, "That student is already in this class")
    # Temporary unique value; the authoritative visible number is assigned after sorting the roster.
    temporary_code = f"TMP-{uuid.uuid4().hex[:10]}"
    student = Student(class_id=data.class_id, student_code=temporary_code, full_name=name)
    db.add(student)
    db.flush()
    renumber_class_students(db, data.class_id)
    audit(db, user.id, "student", student.id, "create", new={"class_id": data.class_id, "full_name": name, "assigned_number": student.student_code})
    db.commit()
    return {"id": student.id, "class_id": student.class_id, "student_code": student.student_code, "full_name": student.full_name}


@app.patch("/api/students/{student_id}")
def update_student(student_id: int, data: StudentIn, db: Session = Depends(get_db), user=Depends(protected)):
    student = db.get(Student, student_id)
    classroom0 = db.get(ClassRoom, student.class_id) if student else None
    if not student or not classroom0 or classroom0.school_id != user.school_id:
        raise HTTPException(404, "Student not found")
    old_class_id = student.class_id
    old = {"class_id": student.class_id, "student_code": student.student_code, "full_name": student.full_name}
    new_name = data.full_name.strip()
    duplicate = db.scalar(select(Student).where(Student.id != student.id, Student.class_id == data.class_id, func.lower(Student.full_name) == new_name.lower(), Student.status == "active"))
    if duplicate:
        raise HTTPException(409, "That student is already in this class")
    student.class_id = data.class_id
    student.full_name = new_name
    target_class = db.get(ClassRoom, data.class_id)
    if not target_class or target_class.school_id != user.school_id:
        raise HTTPException(404, "Class not found")
    db.flush()
    renumber_class_students(db, old_class_id)
    renumber_class_students(db, data.class_id)
    audit(db, user.id, "student", student.id, "update", old=old, new={"class_id": student.class_id, "full_name": student.full_name, "student_code": student.student_code})
    db.commit()
    return {"id": student.id, "class_id": student.class_id, "student_code": student.student_code, "full_name": student.full_name}


@app.post("/api/students/import")
async def import_students(class_id: int = Form(...), upload: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, class_id)
    if not classroom or classroom.status != "active" or classroom.school_id != user.school_id:
        raise HTTPException(404, "Active class not found")
    if upload.content_type not in {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"} and not (upload.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Upload a CSV file")
    raw = await upload.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "CSV file exceeds 2 MB")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except Exception as exc:
        raise HTTPException(400, "CSV could not be read as UTF-8") from exc
    if not reader.fieldnames or "full_name" not in {h.strip().lower() for h in reader.fieldnames if h}:
        raise HTTPException(400, "CSV must contain a full_name column")
    name_key = next(h for h in reader.fieldnames if h and h.strip().lower() == "full_name")
    existing = {s.full_name.casefold() for s in db.scalars(select(Student).where(Student.class_id == class_id, Student.status == "active")).all()}
    added = 0; skipped = 0; errors = 0
    for row in reader:
        name = (row.get(name_key) or "").strip()
        if not name or name.casefold() in existing:
            skipped += 1; continue
        db.add(Student(class_id=class_id, student_code=f"TMP-{uuid.uuid4().hex[:10]}", full_name=name)); existing.add(name.casefold()); added += 1
        if added >= 5000:
            break
    db.flush(); renumber_class_students(db, class_id)
    audit(db, user.id, "student_import", class_id, "import", new={"added": added, "skipped": skipped, "errors": errors})
    db.commit()
    return {"ok": True, "added": added, "skipped": skipped, "errors": errors}


@app.get("/api/subjects")
def subjects(db: Session = Depends(get_db), user=Depends(protected)):
    return [{"id": s.id, "name": s.name, "status": s.status} for s in db.scalars(select(Subject).where(Subject.status == "active", Subject.school_id == user.school_id).order_by(Subject.name)).all()]


@app.post("/api/subjects")
def create_subject(data: SubjectIn, db: Session = Depends(get_db), user=Depends(protected)):
    school = school_or_404(db, user)
    duplicate = db.scalar(select(Subject).where(Subject.school_id == school.id, func.lower(Subject.name) == data.name.strip().lower()))
    if duplicate:
        raise HTTPException(409, "Subject already exists")
    subject = Subject(school_id=school.id, name=data.name.strip())
    db.add(subject); db.flush(); audit(db, user.id, "subject", subject.id, "create", new=data.model_dump()); db.commit()
    return {"id": subject.id, "name": subject.name}


@app.patch("/api/subjects/{subject_id}")
def update_subject(subject_id: int, data: SubjectIn, db: Session = Depends(get_db), user=Depends(protected)):
    subject = db.get(Subject, subject_id)
    if not subject or subject.school_id != user.school_id:
        raise HTTPException(404, "Subject not found")
    old = subject.name; subject.name = data.name.strip(); audit(db, user.id, "subject", subject.id, "update", old={"name": old}, new=data.model_dump()); db.commit()
    return {"id": subject.id, "name": subject.name}


@app.post("/api/subjects/{subject_id}/archive")
def archive_subject(subject_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    subject = db.get(Subject, subject_id)
    if not subject or subject.school_id != user.school_id:
        raise HTTPException(404, "Subject not found")
    old = subject.status
    subject.status = "archived"
    audit(db, user.id, "subject", subject.id, "archive", old={"status": old}, new={"status": subject.status})
    db.commit()
    return {"ok": True}


@app.get("/api/assessment-types")
def assessment_types(db: Session = Depends(get_db), user=Depends(protected)):
    return [
        {"id": a.id, "name": a.name, "max_score": a.max_score, "weight": a.weight, "enabled": a.enabled, "sort_order": a.sort_order}
        for a in db.scalars(select(AssessmentType).where(AssessmentType.school_id == user.school_id).order_by(AssessmentType.sort_order, AssessmentType.name)).all()
    ]


@app.post("/api/assessment-types")
def create_assessment_type(data: AssessmentTypeIn, db: Session = Depends(get_db), user=Depends(protected)):
    school = school_or_404(db, user)
    a = AssessmentType(school_id=school.id, **data.model_dump())
    db.add(a); db.flush(); audit(db, user.id, "assessment_type", a.id, "create", new=data.model_dump()); db.commit()
    return {"id": a.id, **data.model_dump()}


@app.patch("/api/assessment-types/{aid}")
def update_assessment_type(aid: int, data: AssessmentTypeIn, db: Session = Depends(get_db), user=Depends(protected)):
    a = db.get(AssessmentType, aid)
    if not a or a.school_id != user.school_id:
        raise HTTPException(404, "Assessment type not found")
    old = {"name": a.name, "max_score": a.max_score, "weight": a.weight, "enabled": a.enabled, "sort_order": a.sort_order}
    for key, value in data.model_dump().items(): setattr(a, key, value)
    audit(db, user.id, "assessment_type", aid, "update", old=old, new=data.model_dump()); db.commit()
    return {"id": a.id, **data.model_dump()}


@app.post("/api/assessment-types/{aid}/archive")
def archive_assessment_type(aid: int, db: Session = Depends(get_db), user=Depends(protected)):
    a = db.get(AssessmentType, aid)
    if not a or a.school_id != user.school_id:
        raise HTTPException(404, "Assessment type not found")
    old = {"enabled": a.enabled}
    a.enabled = False
    audit(db, user.id, "assessment_type", aid, "disable", old=old, new={"enabled": False})
    db.commit()
    return {"ok": True}


@app.get("/api/assessments")
def assessments(class_id: int | None = None, subject_id: int | None = None, db: Session = Depends(get_db), user=Depends(protected)):
    stmt = select(Assessment, AssessmentType, Subject).join(AssessmentType, Assessment.assessment_type_id == AssessmentType.id).join(Subject, Assessment.subject_id == Subject.id).where(Assessment.status == "active", AssessmentType.school_id == user.school_id, Subject.school_id == user.school_id)
    if class_id is not None: stmt = stmt.where((Assessment.class_id == class_id) | (Assessment.class_id.is_(None)))
    if subject_id is not None: stmt = stmt.where(Assessment.subject_id == subject_id)
    rows = db.execute(stmt.order_by(Assessment.date.desc(), Assessment.title)).all()
    return [{"id": a.id, "title": a.title, "date": str(a.date), "type_id": t.id, "type": t.name, "max_score": t.max_score, "weight": t.weight, "enabled": t.enabled, "grading_mode": a.grading_mode, "subject_id": s.id, "subject": s.name, "class_id": a.class_id} for a, t, s in rows]


@app.post("/api/assessments")
def create_assessment(data: AssessmentIn, db: Session = Depends(get_db), user=Depends(protected)):
    assessment_type = db.get(AssessmentType, data.assessment_type_id)
    if not assessment_type or assessment_type.school_id != user.school_id: raise HTTPException(404, "Assessment type not found")
    if not assessment_type.enabled: raise HTTPException(400, "This assessment type is disabled")
    subject = db.get(Subject, data.subject_id)
    if not subject or subject.school_id != user.school_id: raise HTTPException(404, "Subject not found")
    if data.class_id is not None and (not db.get(ClassRoom, data.class_id) or db.get(ClassRoom, data.class_id).school_id != user.school_id): raise HTTPException(404, "Class not found")
    obj = Assessment(**data.model_dump())
    db.add(obj); db.flush(); audit(db, user.id, "assessment", obj.id, "create", new=data.model_dump()); db.commit()
    return {"id": obj.id, **data.model_dump(), "date": str(obj.date)}


@app.patch("/api/assessments/{assessment_id}")
def update_assessment(assessment_id: int, data: AssessmentIn, db: Session = Depends(get_db), user=Depends(protected)):
    obj = db.get(Assessment, assessment_id)
    at = db.get(AssessmentType, obj.assessment_type_id) if obj else None
    if not obj or not at or at.school_id != user.school_id: raise HTTPException(404, "Assessment not found")
    old = {"assessment_type_id": obj.assessment_type_id, "subject_id": obj.subject_id, "title": obj.title, "date": str(obj.date), "class_id": obj.class_id}
    for key, value in data.model_dump().items(): setattr(obj, key, value)
    audit(db, user.id, "assessment", obj.id, "update", old=old, new=data.model_dump()); db.commit()
    return {"id": obj.id, **data.model_dump(), "date": str(obj.date)}


@app.post("/api/assessments/{assessment_id}/archive")
def archive_assessment(assessment_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    obj = db.get(Assessment, assessment_id)
    at = db.get(AssessmentType, obj.assessment_type_id) if obj else None
    if not obj or not at or at.school_id != user.school_id: raise HTTPException(404, "Assessment not found")
    obj.status = "archived"; audit(db, user.id, "assessment", obj.id, "archive", new={"status":"archived"}); db.commit()
    return {"ok": True}


@app.get("/api/scores")
def score_grid(assessment_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    assessment = db.get(Assessment, assessment_id)
    if not assessment: raise HTTPException(404, "Assessment not found")
    assessment_type = db.get(AssessmentType, assessment.assessment_type_id)
    subject = db.get(Subject, assessment.subject_id)
    if not assessment_type or assessment_type.school_id != user.school_id or not subject or subject.school_id != user.school_id:
        raise HTTPException(404, "Assessment not found")
    stmt = select(Student).join(ClassRoom, Student.class_id == ClassRoom.id).where(Student.status == "active", ClassRoom.school_id == user.school_id)
    if assessment.class_id is not None: stmt = stmt.where(Student.class_id == assessment.class_id)
    students = db.scalars(stmt.order_by(Student.full_name)).all()
    rows = []
    for student in students:
        score = db.scalar(select(StudentScore).where(StudentScore.student_id == student.id, StudentScore.assessment_id == assessment_id))
        rows.append({"student_id": student.id, "student": student.full_name, "code": student.student_code, "score": score.score if score else None, "status": score.status if score else "empty"})
    return rows


@app.post("/api/scores")
def save_score(data: ScoreIn, db: Session = Depends(get_db), user=Depends(protected)):
    assessment = db.get(Assessment, data.assessment_id)
    student = db.get(Student, data.student_id)
    if not assessment or not student: raise HTTPException(404, "Assessment or student not found")
    assessment_type = db.get(AssessmentType, assessment.assessment_type_id)
    student_class = db.get(ClassRoom, student.class_id)
    subject = db.get(Subject, assessment.subject_id)
    if not assessment_type or assessment_type.school_id != user.school_id or not subject or subject.school_id != user.school_id or not student_class or student_class.school_id != user.school_id:
        raise HTTPException(404, "Assessment or student not found")
    if assessment.class_id is not None and student.class_id != assessment.class_id: raise HTTPException(400, "Student does not belong to this assessment class")
    at = assessment_type
    if data.status == "entered":
        if data.score is None: raise HTTPException(400, "Enter a score for entered status")
        if data.score > at.max_score: raise HTTPException(400, f"Score cannot exceed {at.max_score}")
    elif data.status == "zero":
        data.score = 0
    row = db.scalar(select(StudentScore).where(StudentScore.student_id == data.student_id, StudentScore.assessment_id == data.assessment_id))
    old = {"score": row.score, "status": row.status} if row else None
    if not row: row = StudentScore(student_id=data.student_id, assessment_id=data.assessment_id)
    row.status = data.status
    row.score = data.score if data.status in {"entered", "zero"} else None
    row.teacher_note = data.teacher_note
    db.add(row)
    audit(db, user.id, "score", row.id, "update", old=old, new={"score": row.score, "status": row.status})
    db.commit()
    return {"ok": True, "student_average": recalc_student(db, data.student_id)}



SYNC_ALLOWED_ROUTES = {"/api/attendance", "/api/attendance/bulk", "/api/scores"}

@app.post("/api/sync")
def sync_batch(data: SyncBatchIn, db: Session = Depends(get_db), user=Depends(protected)):
    """Apply idempotent offline-first mutations. The server remains authoritative."""
    results = []
    for op in data.operations:
        if op.path not in SYNC_ALLOWED_ROUTES or op.method != "POST":
            results.append({"operation_id": op.operation_id, "status": "rejected", "reason": "Route not allowed for offline sync"})
            continue
        existing = db.scalar(select(SyncOperation).where(SyncOperation.operation_id == op.operation_id, SyncOperation.user_id == user.id))
        if existing:
            results.append({"operation_id": op.operation_id, "status": "already_applied"})
            continue
        try:
            with db.begin_nested():
                if op.path == "/api/attendance":
                    payload = AttendanceIn.model_validate(op.body)
                    student = db.get(Student, payload.student_id)
                    classroom = db.get(ClassRoom, student.class_id) if student else None
                    if not student or not classroom or classroom.school_id != user.school_id:
                        raise ValueError("Student not found")
                    row = db.scalar(select(Attendance).where(Attendance.student_id == payload.student_id, Attendance.date == payload.date))
                    old = {"status": row.status} if row else None
                    if not row: row = Attendance(student_id=payload.student_id, date=payload.date, status=payload.status)
                    else: row.status = payload.status
                    db.add(row); db.flush()
                    audit(db, user.id, "attendance", row.id, "sync_upsert", old=old, new={"status": row.status, "date": str(row.date), "offline_operation_id": op.operation_id})
                elif op.path == "/api/attendance/bulk":
                    raw_date = op.body.get("date")
                    attendance_date = date.fromisoformat(str(raw_date))
                    status = str(op.body.get("status") or "present")
                    ids = op.body.get("student_ids") or []
                    if status not in {"present","absent","late","excused"} or not isinstance(ids, list):
                        raise ValueError("Invalid attendance payload")
                    for sid in sorted(set(int(x) for x in ids)):
                        student = db.get(Student, sid); classroom = db.get(ClassRoom, student.class_id) if student else None
                        if not student or not classroom or classroom.school_id != user.school_id: raise ValueError("Student does not belong to this workspace")
                        row = db.scalar(select(Attendance).where(Attendance.student_id == sid, Attendance.date == attendance_date))
                        if not row: row = Attendance(student_id=sid, date=attendance_date, status=status)
                        else: row.status = status
                        db.add(row)
                elif op.path == "/api/scores":
                    payload = ScoreIn.model_validate(op.body)
                    assessment = db.get(Assessment, payload.assessment_id); student = db.get(Student, payload.student_id)
                    at = db.get(AssessmentType, assessment.assessment_type_id) if assessment else None
                    classroom = db.get(ClassRoom, student.class_id) if student else None
                    subject = db.get(Subject, assessment.subject_id) if assessment else None
                    if not assessment or not student or not at or at.school_id != user.school_id or not classroom or classroom.school_id != user.school_id or not subject or subject.school_id != user.school_id:
                        raise ValueError("Assessment or student not found")
                    if assessment.class_id is not None and student.class_id != assessment.class_id: raise ValueError("Student does not belong to assessment class")
                    if payload.status == "entered" and (payload.score is None or payload.score > at.max_score): raise ValueError("Invalid score")
                    score_value = 0 if payload.status == "zero" else (payload.score if payload.status in {"entered","zero"} else None)
                    row = db.scalar(select(StudentScore).where(StudentScore.student_id == student.id, StudentScore.assessment_id == assessment.id))
                    if not row: row = StudentScore(student_id=student.id, assessment_id=assessment.id)
                    row.status = payload.status; row.score = score_value; row.teacher_note = payload.teacher_note; db.add(row); db.flush()
                db.add(SyncOperation(operation_id=op.operation_id, user_id=user.id, route=op.path, method=op.method))
            results.append({"operation_id": op.operation_id, "status": "applied"})
        except Exception as exc:
            results.append({"operation_id": op.operation_id, "status": "failed", "reason": str(exc)})
    db.commit()
    return {"ok": True, "results": results}

@app.get("/api/attendance/last-date")
def attendance_last_date(class_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, class_id)
    if not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Class not found")
    student_ids = select(Student.id).where(Student.class_id == class_id)
    latest = db.scalar(select(func.max(Attendance.date)).where(Attendance.student_id.in_(student_ids)))
    return {"latest_date": str(latest) if latest else None, "today": str(date.today())}

@app.get("/api/attendance/history")
def attendance_history(class_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, class_id)
    if not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Class not found")
    student_ids = select(Student.id).where(Student.class_id == class_id)
    rows = db.scalars(select(Attendance.date).where(Attendance.student_id.in_(student_ids)).distinct().order_by(Attendance.date.desc())).all()
    return {"dates": [str(x) for x in rows]}

@app.get("/api/attendance")
def get_attendance(class_id: int, attendance_date: date | None = None, db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, class_id)
    if not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Class not found")
    d = attendance_date or date.today()
    students = db.scalars(select(Student).where(Student.class_id == class_id, Student.status == "active").order_by(Student.full_name)).all()
    rows = []
    for student in students:
        record = db.scalar(select(Attendance).where(Attendance.student_id == student.id, Attendance.date == d))
        rows.append({"student_id": student.id, "student": student.full_name, "code": student.student_code, "status": record.status if record else None, "recorded": bool(record)})
    return {"date": str(d), "rows": rows}


@app.post("/api/attendance/bulk")
def save_attendance_bulk(data: dict, db: Session = Depends(get_db), user=Depends(protected)):
    raw_date=data.get("date")
    try:
        attendance_date=date.fromisoformat(str(raw_date))
    except Exception as exc:
        raise HTTPException(400, "Invalid attendance date") from exc
    status=str(data.get("status") or "present")
    if status not in {"present","absent","late","excused"}:
        raise HTTPException(400, "Invalid attendance status")
    student_ids=data.get("student_ids") or []
    if not isinstance(student_ids,list) or len(student_ids)>5000:
        raise HTTPException(400,"Invalid student list")
    saved=0
    for sid in sorted(set(int(x) for x in student_ids)):
        student=db.get(Student,sid)
        classroom = db.get(ClassRoom, student.class_id) if student else None
        if not student or not classroom or classroom.school_id != user.school_id: continue
        row=db.scalar(select(Attendance).where(Attendance.student_id==sid, Attendance.date==attendance_date))
        old={"status":row.status} if row else None
        if not row: row=Attendance(student_id=sid,date=attendance_date)
        row.status=status; db.add(row); db.flush()
        audit(db,user.id,"attendance",row.id,"upsert",old=old,new={"status":status,"date":str(attendance_date)})
        saved+=1
    db.commit()
    return {"ok":True,"date":str(attendance_date),"saved":saved,"status":status}

@app.post("/api/attendance")
def save_attendance(data: AttendanceIn, db: Session = Depends(get_db), user=Depends(protected)):
    student = db.get(Student, data.student_id)
    classroom = db.get(ClassRoom, student.class_id) if student else None
    if not student or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Student not found")
    row = db.scalar(select(Attendance).where(Attendance.student_id == data.student_id, Attendance.date == data.date))
    old = {"status": row.status} if row else None
    if not row: row = Attendance(student_id=data.student_id, date=data.date)
    row.status = data.status; db.add(row)
    audit(db, user.id, "attendance", row.id, "upsert", old=old, new={"status": row.status, "date": str(row.date)})
    db.commit()
    return {"ok": True, "date": str(data.date), "student_id": data.student_id, "status": data.status}


@app.get("/api/analytics/class/{class_id}")
def class_analytics(class_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, class_id)
    if not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Class not found")
    students = db.scalars(select(Student).where(Student.class_id == class_id, Student.status == "active")).all()
    metrics = roster_metrics(db, [s.id for s in students])
    avgs = [metrics.get(s.id, {}).get("average", 0) for s in students]
    attendance = [metrics.get(s.id, {}).get("attendance", 0) for s in students]
    mistakes = db.execute(select(Mistake.mistake_type, func.sum(Mistake.occurrence_count)).where(Mistake.student_id.in_([s.id for s in students]) if students else False).group_by(Mistake.mistake_type).order_by(func.sum(Mistake.occurrence_count).desc())).all() if students else []
    school = school_or_404(db, user)
    return {"average": round(sum(avgs) / len(avgs), 1) if avgs else 0, "highest": max(avgs, default=0), "lowest": min(avgs, default=0), "pass_rate": round(sum(a >= school.pass_mark for a in avgs) / len(avgs) * 100, 1) if avgs else 0, "attendance": round(sum(attendance) / len(attendance), 1) if attendance else 0, "students_needing_support": sum(a < school.pass_mark for a in avgs), "pass_mark": school.pass_mark, "top_mistake": mistakes[0][0] if mistakes else "No evidence yet", "rankings": class_rankings(db, class_id)}


@app.get("/api/students/{student_id}/profile")
def student_profile(student_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    student = db.get(Student, student_id)
    classroom = db.get(ClassRoom, student.class_id) if student else None
    if not student or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Student not found")
    mistakes = db.scalars(select(Mistake).where(Mistake.student_id == student_id).order_by(Mistake.occurrence_count.desc())).all()
    recent = db.scalars(select(Submission).where(Submission.student_id == student_id).order_by(Submission.created_at.desc()).limit(12)).all()
    score_rows = db.execute(select(StudentScore, Assessment, AssessmentType).join(Assessment, StudentScore.assessment_id == Assessment.id).join(AssessmentType, Assessment.assessment_type_id == AssessmentType.id).where(StudentScore.student_id == student_id).order_by(Assessment.date.desc()).limit(20)).all()
    school = school_or_404(db, user)
    assessments = []
    for score, assessment, at in score_rows:
        pct = round((score.score or 0) / at.max_score * 100, 1) if at.max_score else 0
        assessments.append({"assessment_id": assessment.id, "title": assessment.title, "date": str(assessment.date), "score": score.score, "max_score": at.max_score, "percent": pct, "passed": pct >= school.pass_mark, "status": score.status})
    return {"student": {"id": student.id, "name": student.full_name, "code": student.student_code, "class_id": student.class_id}, "overall": recalc_student(db, student_id), "pass_mark": school.pass_mark, "attendance": attendance_summary(db, student_id), "assessments": assessments, "mistakes": [{"topic": m.topic, "mistake_type": m.mistake_type, "occurrences": m.occurrence_count, "last_seen": str(m.last_seen)} for m in mistakes], "strengths": [], "weaknesses": [m.topic for m in mistakes[:4]], "recommendations": [f"Review {mistakes[0].topic} and practise targeted questions." if mistakes else "Collect more assessment evidence before recommending a topic."], "recent_ai_checks": [{"submission_id": s.id, "exam_id": s.exam_id, "status": s.status, "detected_name": s.detected_name, "identity_confidence": s.identity_confidence, "created_at": s.created_at.isoformat()} for s in recent]}


@app.get("/api/exams")
def exams(db: Session = Depends(get_db), user=Depends(protected)):
    rows = db.execute(select(Exam, Subject, ClassRoom).join(Subject, Exam.subject_id == Subject.id).join(ClassRoom, Exam.class_id == ClassRoom.id).where(ClassRoom.school_id == user.school_id, Subject.school_id == user.school_id).order_by(Exam.created_at.desc())).all()
    return [{"id": e.id, "title": e.title, "total_marks": e.total_marks, "assessment_id": e.assessment_id, "subject": s.name, "subject_id": s.id, "class_id": c.id, "class_name": c.name} for e, s, c in rows]


@app.post("/api/exams")
def create_exam(data: ExamIn, db: Session = Depends(get_db), user=Depends(protected)):
    classroom = db.get(ClassRoom, data.class_id)
    subject = db.get(Subject, data.subject_id)
    if not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Class not found")
    if not subject or subject.school_id != user.school_id: raise HTTPException(404, "Subject not found")
    if data.assessment_id is not None:
        linked = db.get(Assessment, data.assessment_id)
        linked_type = db.get(AssessmentType, linked.assessment_type_id) if linked else None
        if not linked or not linked_type or linked_type.school_id != user.school_id: raise HTTPException(404, "Assessment not found")
    exam = Exam(**data.model_dump()); db.add(exam); db.flush(); audit(db, user.id, "exam", exam.id, "create", new=data.model_dump()); db.commit()
    return {"id": exam.id, **data.model_dump()}


@app.get("/api/exams/{exam_id}/questions")
def exam_questions(exam_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    exam = db.get(Exam, exam_id)
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Exam not found")
    return [{"id": q.id, "question_no": q.question_no, "question_text": q.question_text, "max_score": q.max_score, "topic": q.topic, "answer_type": q.answer_type} for q in db.scalars(select(Question).where(Question.exam_id == exam_id).order_by(Question.question_no)).all()]


@app.post("/api/questions")
def create_question(data: QuestionIn, db: Session = Depends(get_db), user=Depends(protected)):
    exam = db.get(Exam, data.exam_id)
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Exam not found")
    if db.scalar(select(Question).where(Question.exam_id == data.exam_id, Question.question_no == data.question_no)):
        raise HTTPException(409, "That question number already exists for this exam")
    q = Question(**data.model_dump()); db.add(q); db.flush(); audit(db, user.id, "question", q.id, "create", new=data.model_dump()); db.commit()
    return {"id": q.id, **data.model_dump()}


def _grade_with_retry(image_path: str, mime_type: str, questions: list[dict], answer_key: str | None):
    last_error = None
    attempts = max(1, settings.ai_max_retries + 1)
    for attempt in range(attempts):
        try:
            return GeminiService().analyze_answer_sheet(image_path, mime_type, questions, answer_key)
        except GeminiUnavailable as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise
            time.sleep(settings.ai_retry_backoff_seconds * (2 ** attempt))
    raise GeminiUnavailable(str(last_error or "Gemini request failed"))


def _question_payload(db: Session, exam_id: int):
    return [
        {"question_id": q.id, "question_no": q.question_no, "question_text": q.question_text,
         "maximum_score": q.max_score, "topic": q.topic or "Unmapped", "answer_type": q.answer_type}
        for q in db.scalars(select(Question).where(Question.exam_id == exam_id).order_by(Question.question_no)).all()
    ]


def _auto_store_submission(db: Session, submission: Submission, user_id: int, force_teacher_review: bool = False):
    if force_teacher_review or not submission.student_id:
        return {"auto_stored": False, "reason": "identity_not_ready"}
    exam = db.get(Exam, submission.exam_id)
    questions = _question_payload(db, submission.exam_id)
    if not exam or not questions or not exam.assessment_id:
        return {"auto_stored": False, "reason": "exam_setup_incomplete"}
    if submission.identity_status != "matched" or (submission.identity_confidence or 0) < settings.identity_auto_accept_threshold:
        return {"auto_stored": False, "reason": "identity_below_threshold"}
    results = db.scalars(select(AIResult).where(AIResult.submission_id == submission.id)).all()
    expected_ids = {q["question_id"] for q in questions}
    actual_ids = [r.question_id for r in results if r.question_id is not None]
    if set(actual_ids) != expected_ids or len(actual_ids) != len(expected_ids):
        return {"auto_stored": False, "reason": "question_coverage_incomplete"}
    if any(r.needs_teacher_review or (r.confidence or 0) < settings.question_auto_accept_threshold for r in results):
        return {"auto_stored": False, "reason": "low_confidence_or_review_required"}
    if any(r.suggested_score is None for r in results):
        return {"auto_stored": False, "reason": "missing_score"}
    assessment = db.get(Assessment, exam.assessment_id)
    at = db.get(AssessmentType, assessment.assessment_type_id) if assessment else None
    if not assessment or not at:
        return {"auto_stored": False, "reason": "assessment_setup_incomplete"}
    existing = db.scalar(select(StudentScore).where(StudentScore.student_id == submission.student_id, StudentScore.assessment_id == assessment.id))
    if existing and existing.status in {"entered", "zero"}:
        submission.status = "score_conflict"
        audit(db, user_id, "submission", submission.id, "auto_store_blocked_conflict", new={"student_id": submission.student_id, "assessment_id": assessment.id})
        return {"auto_stored": False, "reason": "existing_final_score"}
    # Reconcile by question maximums rather than trusting model totals.
    max_by_question = {q["question_id"]: float(q["maximum_score"]) for q in questions}
    earned = sum(min(max(float(r.suggested_score or 0), 0), max_by_question.get(r.question_id, 0.0)) for r in results)
    question_total = sum(max_by_question.values())
    ratio = max(0.0, min(1.0, earned / question_total if question_total else 0.0))
    score_row = existing or StudentScore(student_id=submission.student_id, assessment_id=assessment.id)
    score_row.score = round(ratio * float(at.max_score), 2)
    score_row.status = "entered"
    db.add(score_row)
    for r in results:
        r.teacher_score = r.suggested_score
        r.review_status = "accepted"
        record_mistake(db, submission.student_id, r.topic, r.mistake_type)
    submission.status = "completed"
    student = db.get(Student, submission.student_id)
    classroom = db.get(ClassRoom, student.class_id) if student else None
    school = db.get(School, classroom.school_id) if classroom else None
    passed = bool(school) and (ratio * 100) >= float(school.pass_mark)
    audit(db, user_id, "score", score_row.id, "ai_auto_commit", new={"score": score_row.score, "passed": passed, "submission_id": submission.id})
    return {"auto_stored": True, "stored_score": score_row.score, "passed": passed, "question_total_marks": question_total}


async def _save_upload(upload: UploadFile, prefix: str = ""):
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Upload a JPG, PNG, or WEBP image")
    data = await upload.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(upload.filename or "sheet.jpg").name)
    raw = Path(settings.upload_dir) / f"{prefix}{uuid.uuid4().hex}_{safe_name}"
    raw.write_bytes(data)
    try:
        prepared = validate_image_and_prepare(raw, upload.content_type)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return raw, prepared


def _process_submission_sync(submission_id: int, user_id: int):
    local = SessionLocal()
    try:
        submission = local.get(Submission, submission_id)
        if not submission:
            return {"ok": False, "reason": "submission_missing"}
        exam = local.get(Exam, submission.exam_id)
        questions = _question_payload(local, submission.exam_id)
        if not exam or not questions:
            submission.status = "needs_exam_setup"
            local.commit()
            return {"ok": False, "reason": "exam_setup_incomplete"}
        try:
            output = _grade_with_retry(submission.stored_path, "image/jpeg", questions, exam.answer_key)
        except GeminiUnavailable as exc:
            submission.status = "ai_failed"
            audit(local, user_id, "submission", submission.id, "ai_failed", new={"error": str(exc)})
            local.commit()
            return {"ok": False, "reason": "ai_failed"}
        submission.detected_name = output.identity.detected_name
        submission.detected_code = output.identity.detected_code
        submission.identity_confidence = output.identity.confidence
        match, match_score, match_reason, _candidates = match_detected_student(local, exam.class_id, output.identity.detected_name, output.identity.detected_code)
        if match and output.identity.confidence >= settings.identity_auto_accept_threshold:
            submission.student_id = match.id
            submission.identity_status = "matched"
        elif match:
            submission.student_id = None
            submission.identity_status = "ambiguous"
        else:
            submission.identity_status = "unmatched"
        valid = {q["question_id"]: q for q in questions}
        seen=set()
        for item in output.questions:
            if item.question_id not in valid or item.question_id in seen:
                continue
            seen.add(item.question_id)
            qmax=float(valid[item.question_id]["maximum_score"])
            needs = item.needs_teacher_review or item.confidence < settings.question_auto_accept_threshold
            local.add(AIResult(submission_id=submission.id, question_id=item.question_id, suggested_score=min(float(item.score), qmax), confidence=item.confidence, reason=item.reason, mistake_type=item.mistake_type, topic=item.topic, feedback=item.feedback, needs_teacher_review=needs or submission.identity_status != "matched", review_status="pending"))
        submission.status = "ai_processed"
        auto = _auto_store_submission(local, submission, user_id)
        local.commit()
        return {"ok": True, "submission_id": submission.id, "match_reason": match_reason, **auto}
    finally:
        local.close()


@app.post("/api/exams/{exam_id}/scan")
async def scan_exam(exam_id: int, upload: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(protected)):
    exam = db.get(Exam, exam_id)
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    assessment = db.get(Assessment, exam.assessment_id) if exam and exam.assessment_id else None
    if not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Exam not found")
    if assessment and assessment.grading_mode != "ai": raise HTTPException(400, "This assessment is configured for teacher-entered scores. Use the score grid instead of AI Checker.")
    _raw, prepared = await _save_upload(upload)
    questions = _question_payload(db, exam_id)
    submission = Submission(exam_id=exam_id, original_filename=upload.filename or "sheet.jpg", stored_path=prepared["processed_path"], status="uploaded", identity_status="unresolved")
    db.add(submission); db.flush()
    result = {"submission_id": submission.id, "quality": prepared["quality"], "status": "manual_review_required", "ai_enabled": bool(settings.gemini_api_key), "identity": None, "ai_results": [], "candidates": [], "auto_stored": False}
    if not questions:
        submission.status = "needs_exam_setup"
        audit(db, user.id, "submission", submission.id, "scan", new={"status": submission.status})
        db.commit(); return {**result, "status": "needs_exam_setup", "message": "Add questions to this exam before AI checking."}
    if settings.gemini_api_key:
        try:
            output = _grade_with_retry(prepared["processed_path"], upload.content_type, questions, exam.answer_key)
            submission.detected_name = output.identity.detected_name
            submission.detected_code = output.identity.detected_code
            submission.identity_confidence = output.identity.confidence
            match, match_score, match_reason, candidates = match_detected_student(db, exam.class_id, output.identity.detected_name, output.identity.detected_code)
            if match and output.identity.confidence >= settings.identity_auto_accept_threshold:
                submission.student_id = match.id; submission.identity_status = "matched"
            elif match:
                submission.identity_status = "ambiguous"
                candidates = [(match_score, match)] + [c for c in candidates if c[1].id != match.id]
            else:
                submission.identity_status = "ambiguous" if candidates else "unmatched"
            valid = {q["question_id"]: q for q in questions}; seen=set()
            for item in output.questions:
                if item.question_id not in valid or item.question_id in seen: continue
                seen.add(item.question_id); qmax=float(valid[item.question_id]["maximum_score"])
                db.add(AIResult(submission_id=submission.id, question_id=item.question_id, suggested_score=min(float(item.score), qmax), confidence=item.confidence, reason=item.reason, mistake_type=item.mistake_type, topic=item.topic, feedback=item.feedback, needs_teacher_review=item.needs_teacher_review or item.confidence < settings.question_auto_accept_threshold or submission.identity_status != "matched", review_status="pending"))
            db.flush()
            auto = _auto_store_submission(db, submission, user.id)
            submission.status = "completed" if auto.get("auto_stored") else "ai_processed"
            result.update({"status": submission.status, "identity": {**output.identity.model_dump(), "matched_student": {"id": match.id, "name": match.full_name, "code": match.student_code} if match else None, "match_score": round(match_score, 3), "match_reason": match_reason}, "candidates": [{"id": s.id, "name": s.full_name, "code": s.student_code, "match_score": round(score, 3)} for score, s in candidates], **auto})
            stored_by_q = {r.question_id: r.id for r in db.scalars(select(AIResult).where(AIResult.submission_id == submission.id)).all()}
            result["ai_results"] = [{**r.model_dump(), "ai_result_id": stored_by_q.get(r.question_id)} for r in output.questions if r.question_id in valid]
        except GeminiUnavailable as exc:
            submission.status = "ai_failed"; result["ai_error"] = str(exc)
    else:
        submission.status = "manual_review_required"; result["message"] = "Gemini is not configured. The paper is stored for manual processing."
    audit(db, user.id, "submission", submission.id, "scan", new={"filename": upload.filename, "status": submission.status, "identity_status": submission.identity_status})
    db.commit(); return result


@app.post("/api/exams/{exam_id}/scan-batch")
async def scan_exam_batch(exam_id: int, uploads: list[UploadFile] = File(...), db: Session = Depends(get_db), user=Depends(protected)):
    exam = db.get(Exam, exam_id)
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    assessment = db.get(Assessment, exam.assessment_id) if exam and exam.assessment_id else None
    if not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Exam not found")
    if assessment and assessment.grading_mode != "ai": raise HTTPException(400, "This assessment is configured for teacher-entered scores.")
    if not settings.gemini_api_key: raise HTTPException(503, "Gemini is not configured")
    if not _question_payload(db, exam_id): raise HTTPException(400, "Add exam questions before scanning papers")
    if not uploads or len(uploads) > settings.max_batch_files: raise HTTPException(400, f"Batch size must be between 1 and {settings.max_batch_files} files")
    job = ScanBatchJob(exam_id=exam_id, created_by=user.id, total_files=len(uploads), status="queued")
    db.add(job); db.flush()
    submission_ids=[]
    for upload in uploads:
        _raw, prepared = await _save_upload(upload, prefix=f"batch_{job.id}_")
        sub = Submission(exam_id=exam_id, batch_job_id=job.id, original_filename=upload.filename or "sheet.jpg", stored_path=prepared["processed_path"], status="queued", identity_status="unresolved")
        db.add(sub); db.flush(); submission_ids.append(sub.id)
    audit(db, user.id, "scan_batch_job", job.id, "create", new={"exam_id": exam_id, "total_files": len(submission_ids)})
    job.status = "processing"
    db.commit()
    executor = ThreadPoolExecutor(max_workers=max(1, min(settings.ai_batch_workers, len(submission_ids))))
    def runner(job_id: int, ids: list[int], uid: int):
        local_executor = executor
        futures = [local_executor.submit(_process_submission_sync, sid, uid) for sid in ids]
        db2 = SessionLocal(); j = db2.get(ScanBatchJob, job_id)
        try:
            for future in as_completed(futures):
                try:
                    result = future.result()
                    j.completed_files += 1
                    if result.get("ok"):
                        j.succeeded_files += 1
                        if result.get("auto_stored"):
                            j.auto_stored_files += 1
                        else:
                            j.review_required_files += 1
                    else:
                        j.failed_files += 1
                except Exception:
                    j.completed_files += 1; j.failed_files += 1
                db2.commit()
            j.status = "completed" if j.failed_files == 0 else ("completed_with_errors" if j.succeeded_files else "failed")
            j.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db2.commit()
        finally:
            db2.close(); local_executor.shutdown(wait=False, cancel_futures=False)
    import threading
    threading.Thread(target=runner, args=(job.id, submission_ids, user.id), daemon=True).start()
    return {"job_id": job.id, "exam_id": exam_id, "total_files": len(submission_ids), "status": job.status}


@app.get("/api/scan-jobs/{job_id}")
def scan_job(job_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    job = db.get(ScanBatchJob, job_id)
    if not job: raise HTTPException(404, "Scan job not found")
    return {"id": job.id, "status": job.status, "status_label": job.status.replace("_", " ").title(), "total_files": job.total_files, "completed_files": job.completed_files, "succeeded_files": job.succeeded_files, "failed_files": job.failed_files, "auto_stored_files": job.auto_stored_files, "review_required_files": job.review_required_files, "progress_percent": round(job.completed_files / job.total_files * 100, 1) if job.total_files else 100, "completed_at": job.completed_at.isoformat() if job.completed_at else None}


@app.post("/api/submissions/{submission_id}/assign-student")
def assign_submission_student(submission_id: int, data: AssignStudentIn, db: Session = Depends(get_db), user=Depends(protected)):
    submission = db.get(Submission, submission_id); student = db.get(Student, data.student_id)
    exam = db.get(Exam, submission.exam_id) if submission else None
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not submission or not student or not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Submission or student not found")
    if student.class_id != exam.class_id: raise HTTPException(400, "Student must belong to the exam class")
    old = {"student_id": submission.student_id, "identity_status": submission.identity_status}
    submission.student_id = student.id; submission.identity_status = "teacher_assigned"
    audit(db, user.id, "submission", submission.id, "assign_student", old=old, new={"student_id": student.id})
    db.commit()
    return {"ok": True, "student": {"id": student.id, "name": student.full_name, "code": student.student_code}}


@app.get("/api/exams/{exam_id}/submissions")
def exam_submissions(exam_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user=Depends(protected)):
    exam = db.get(Exam, exam_id)
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Exam not found")
    rows = db.scalars(select(Submission).where(Submission.exam_id == exam_id).order_by(Submission.created_at.desc()).limit(limit)).all()
    return [{"id": s.id, "status": s.status, "identity_status": s.identity_status, "detected_name": s.detected_name, "detected_code": s.detected_code, "identity_confidence": s.identity_confidence, "student_id": s.student_id, "created_at": s.created_at.isoformat()} for s in rows]


@app.get("/api/submissions/{submission_id}")
def get_submission(submission_id: int, db: Session = Depends(get_db), user=Depends(protected)):
    submission = db.get(Submission, submission_id)
    exam = db.get(Exam, submission.exam_id) if submission else None
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not submission or not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Submission not found")
    results = db.scalars(select(AIResult).where(AIResult.submission_id == submission.id).order_by(AIResult.id)).all()
    student = db.get(Student, submission.student_id) if submission.student_id else None
    question_map = {q.id: q for q in db.scalars(select(Question).where(Question.exam_id == submission.exam_id)).all()}
    return {"id": submission.id, "exam_id": submission.exam_id, "student": {"id": student.id, "name": student.full_name, "code": student.student_code} if student else None, "detected_name": submission.detected_name, "detected_code": submission.detected_code, "identity_confidence": submission.identity_confidence, "identity_status": submission.identity_status, "status": submission.status, "results": [{"id": r.id, "question_id": r.question_id, "maximum_score": question_map.get(r.question_id).max_score if r.question_id in question_map else 0, "suggested_score": r.suggested_score, "confidence": r.confidence, "reason": r.reason, "mistake_type": r.mistake_type, "topic": r.topic, "feedback": r.feedback, "needs_teacher_review": r.needs_teacher_review, "teacher_score": r.teacher_score, "review_status": r.review_status} for r in results]}


def finalize_submission_score(db: Session, submission: Submission, user_id: int):
    if not submission.student_id:
        return False
    results = db.scalars(select(AIResult).where(AIResult.submission_id == submission.id)).all()
    if not results or not all(r.review_status in {"accepted", "edited", "rejected"} for r in results):
        return False
    exam = db.get(Exam, submission.exam_id)
    if not exam or not exam.assessment_id:
        return False
    earned = sum((r.teacher_score if r.teacher_score is not None else (r.suggested_score or 0)) for r in results if r.review_status != "rejected")
    ratio = max(0.0, min(1.0, earned / exam.total_marks if exam.total_marks else 0.0))
    assessment = db.get(Assessment, exam.assessment_id)
    at = db.get(AssessmentType, assessment.assessment_type_id) if assessment else None
    if not at:
        return False
    score_row = db.scalar(select(StudentScore).where(StudentScore.student_id == submission.student_id, StudentScore.assessment_id == exam.assessment_id))
    if score_row and score_row.status in {"entered", "zero"} and score_row.id:
        return False
    if not score_row:
        score_row = StudentScore(student_id=submission.student_id, assessment_id=exam.assessment_id)
    score_row.score = round(ratio * at.max_score, 2)
    score_row.status = "entered"
    db.add(score_row)
    submission.status = "completed"
    audit(db, user_id, "score", score_row.id, "ai_exam_commit", new={"score": score_row.score, "submission_id": submission.id})
    return True


@app.post("/api/ai-results/{result_id}/review")
def review_result(result_id: int, data: ReviewIn, db: Session = Depends(get_db), user=Depends(protected)):
    ar = db.get(AIResult, result_id)
    if not ar: raise HTTPException(404, "AI result not found")
    submission = db.get(Submission, ar.submission_id)
    exam = db.get(Exam, submission.exam_id) if submission else None
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not submission or not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "AI result not found")
    question = db.get(Question, ar.question_id) if ar.question_id else None
    if data.action in {"accept", "edit"} and not submission.student_id:
        raise HTTPException(400, "Assign this paper to a student before accepting a score")
    maximum = question.max_score if question else ar.suggested_score or 0
    if data.teacher_score > maximum: raise HTTPException(400, f"Score cannot exceed {maximum}")
    old = {"teacher_score": ar.teacher_score, "review_status": ar.review_status}
    ar.teacher_score = data.teacher_score
    ar.review_status = {"accept": "accepted", "edit": "edited", "reject": "rejected", "recheck": "recheck"}[data.action]
    if question and submission.student_id and data.action in {"accept", "edit"}:
        record_mistake(db, submission.student_id, ar.topic or question.topic or "Unmapped", ar.mistake_type)
    audit(db, user.id, "ai_result", result_id, "teacher_review", old=old, new={"teacher_score": ar.teacher_score, "review_status": ar.review_status}, reason=data.reason)
    finalize_submission_score(db, submission, user.id)
    db.commit()
    return {"ok": True, "review_status": ar.review_status}


@app.post("/api/submissions/{submission_id}/approve-high-confidence")
def approve_high_confidence(submission_id: int, threshold: float = Query(0.9, ge=0, le=1), db: Session = Depends(get_db), user=Depends(protected)):
    submission = db.get(Submission, submission_id)
    exam = db.get(Exam, submission.exam_id) if submission else None
    classroom = db.get(ClassRoom, exam.class_id) if exam else None
    if not submission or not exam or not classroom or classroom.school_id != user.school_id: raise HTTPException(404, "Submission not found")
    if not submission.student_id: raise HTTPException(400, "Assign this paper to a student first")
    results = db.scalars(select(AIResult).where(AIResult.submission_id == submission.id, AIResult.review_status == "pending")).all()
    approved = 0
    for ar in results:
        if (ar.confidence or 0) >= threshold and not ar.needs_teacher_review:
            ar.teacher_score = ar.suggested_score
            ar.review_status = "accepted"
            question = db.get(Question, ar.question_id) if ar.question_id else None
            record_mistake(db, submission.student_id, ar.topic or (question.topic if question else None), ar.mistake_type)
            approved += 1
    audit(db, user.id, "submission", submission.id, "bulk_accept_high_confidence", new={"threshold": threshold, "approved": approved})
    finalize_submission_score(db, submission, user.id)
    db.commit()
    return {"ok": True, "approved": approved, "threshold": threshold}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(protected)):
    students = db.scalars(select(Student).join(ClassRoom, Student.class_id == ClassRoom.id).where(Student.status == "active", ClassRoom.school_id == user.school_id)).all()
    metrics = roster_metrics(db, [s.id for s in students])
    missing = db.scalar(select(func.count(StudentScore.id)).join(Assessment, StudentScore.assessment_id == Assessment.id).join(AssessmentType, Assessment.assessment_type_id == AssessmentType.id).where(StudentScore.status == "empty", AssessmentType.school_id == user.school_id)) or 0
    pending = db.scalar(select(func.count(AIResult.id)).join(Submission, AIResult.submission_id == Submission.id).join(Exam, Submission.exam_id == Exam.id).join(ClassRoom, Exam.class_id == ClassRoom.id).where(AIResult.needs_teacher_review == True, AIResult.review_status == "pending", ClassRoom.school_id == user.school_id)) or 0
    submissions = db.scalar(select(func.count(Submission.id)).join(Exam, Submission.exam_id == Exam.id).join(ClassRoom, Exam.class_id == ClassRoom.id).where(Submission.status.in_(["completed", "ai_processed", "ai_failed", "manual_review_required"]), ClassRoom.school_id == user.school_id)) or 0
    school = school_or_404(db, user)
    support = sum(1 for s in students if metrics.get(s.id, {}).get("average", 0) < school.pass_mark)
    return {"students": len(students), "missing_scores": missing, "pending_ai_reviews": pending, "students_needing_attention": support, "classes": db.scalar(select(func.count(ClassRoom.id)).where(ClassRoom.status == "active", ClassRoom.school_id == user.school_id)) or 0, "submissions": submissions, "pass_mark": school.pass_mark}


@app.get("/api/reports/student/{student_id}")
def student_report(student_id: int, report_type: str = Query("overview"), db: Session = Depends(get_db), user=Depends(protected)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    classroom = db.get(ClassRoom, student.class_id)
    if not classroom or classroom.school_id != user.school_id:
        raise HTTPException(404, "Student not found")
    school = school_or_404(db, user)
    attendance_rows = db.scalars(select(Attendance).where(Attendance.student_id == student_id).order_by(Attendance.date.desc())).all()
    score_rows = db.execute(select(StudentScore, Assessment, AssessmentType).join(Assessment, StudentScore.assessment_id == Assessment.id).join(AssessmentType, Assessment.assessment_type_id == AssessmentType.id).where(StudentScore.student_id == student_id).order_by(Assessment.date.desc())).all()
    assessments=[]
    for score, assessment, at in score_rows:
        pct = round((score.score / at.max_score) * 100, 1) if score.score is not None and at.max_score else None
        assessments.append({"assessment_id": assessment.id, "title": assessment.title, "date": str(assessment.date), "assessment_type": at.name, "score": score.score, "max_score": at.max_score, "percent": pct, "status": score.status, "passed": pct is not None and pct >= school.pass_mark})
    rtype = report_type.lower().strip()
    if rtype == "attendance":
        payload = {"type":"attendance","student":student.full_name,"code":student.student_code,"class_id":student.class_id,"attendance": [{"date":str(r.date),"status":r.status} for r in attendance_rows],"summary":attendance_summary(db, student_id)}
    elif rtype == "score":
        payload = {"type":"score","student":student.full_name,"code":student.student_code,"assessments":assessments}
    elif rtype in {"midterm","final"}:
        key=rtype
        filtered=[a for a in assessments if key in (a["title"]+" "+a["assessment_type"]).lower()]
        payload = {"type":rtype,"student":student.full_name,"code":student.student_code,"pass_mark":school.pass_mark,"assessments":filtered,"average": round(sum(a["percent"] for a in filtered if a["percent"] is not None)/len([a for a in filtered if a["percent"] is not None]),1) if any(a["percent"] is not None for a in filtered) else 0}
    elif rtype == "transcript":
        payload = {"type":"transcript","student":student.full_name,"code":student.student_code,"pass_mark":school.pass_mark,"overall":recalc_student(db, student_id),"attendance":attendance_summary(db, student_id),"assessments":assessments}
    else:
        payload = {"type":"overview","student":student.full_name,"code":student.student_code,"overall":recalc_student(db, student_id),"attendance":attendance_summary(db, student_id),"assessments":assessments[:30],"mistakes":[{"topic":x.topic,"mistake_type":x.mistake_type,"occurrences":x.occurrence_count} for x in db.scalars(select(Mistake).where(Mistake.student_id==student_id).order_by(Mistake.occurrence_count.desc())).all()[:10]]}
    return payload

@app.get("/api/reports/student/{student_id}/csv")
def student_report_csv(student_id: int, report_type: str = Query("overview"), db: Session = Depends(get_db), user=Depends(protected)):
    data = student_report(student_id, report_type, db, user)
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(["student",data.get("student",""),"report_type",data.get("type",report_type)])
    if data.get("type")=="attendance":
        writer.writerow(["date","status"])
        for row in data["attendance"]: writer.writerow([row["date"],row["status"]])
    else:
        writer.writerow(["assessment","date","type","score","max_score","percent","status","passed"])
        for row in data.get("assessments",[]): writer.writerow([row["title"],row["date"],row["assessment_type"],row["score"],row["max_score"],row["percent"],row["status"],row["passed"]])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition":f"attachment; filename=student-{student_id}-{report_type}.csv"})

@app.get("/api/export/students.csv")
def export_students(db: Session = Depends(get_db), user=Depends(protected)):
    output = io.StringIO(); writer = csv.writer(output)
    students = db.scalars(select(Student).where(Student.status == "active").order_by(Student.full_name)).all()
    metrics = roster_metrics(db, [student.id for student in students])
    writer.writerow(["student_code", "full_name", "class_id", "average", "attendance_percent"])
    for student in students:
        metric = metrics.get(student.id, {"average": 0.0, "attendance": 0.0})
        writer.writerow([student.student_code, student.full_name, student.class_id, metric["average"], metric["attendance"]])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=students.csv"})
