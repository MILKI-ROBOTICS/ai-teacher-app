from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import School, ClassRoom, Subject, AssessmentType, Assessment, Student, StudentScore, Attendance
from app.services import recalc_student, class_rankings, attendance_summary, record_mistake


def db():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(s):
    school = School(name='Test School', academic_year='2026/27'); s.add(school); s.flush()
    classroom = ClassRoom(school_id=school.id, name='10A', grade_level='10'); s.add(classroom); s.flush()
    subject = Subject(school_id=school.id, name='Math'); s.add(subject); s.flush()
    test = AssessmentType(school_id=school.id, name='Test', max_score=20, weight=20, enabled=True, sort_order=1)
    final = AssessmentType(school_id=school.id, name='Final', max_score=50, weight=80, enabled=True, sort_order=2)
    s.add_all([test, final]); s.flush()
    a1 = Assessment(assessment_type_id=test.id, subject_id=subject.id, title='T1', date=date.today(), class_id=classroom.id)
    a2 = Assessment(assessment_type_id=final.id, subject_id=subject.id, title='Final', date=date.today(), class_id=classroom.id)
    s.add_all([a1, a2]); s.flush()
    st1 = Student(class_id=classroom.id, student_code='1', full_name='A')
    st2 = Student(class_id=classroom.id, student_code='2', full_name='B')
    st3 = Student(class_id=classroom.id, student_code='3', full_name='C')
    s.add_all([st1, st2, st3]); s.commit()
    return classroom, a1, a2, st1, st2, st3


def test_empty_student_has_no_average():
    s = db(); classroom, a1, a2, st1, *_ = seed(s)
    assert recalc_student(s, st1.id) == 0


def test_weighted_average_normalizes_available_evidence():
    s = db(); _, a1, a2, st1, *_ = seed(s)
    s.add_all([
        StudentScore(student_id=st1.id, assessment_id=a1.id, score=10, status='entered'),
        StudentScore(student_id=st1.id, assessment_id=a2.id, score=25, status='entered'),
    ]); s.commit()
    assert recalc_student(s, st1.id) == 50.0


def test_missing_and_absent_are_not_zero():
    s = db(); _, a1, a2, st1, *_ = seed(s)
    s.add_all([
        StudentScore(student_id=st1.id, assessment_id=a1.id, score=10, status='entered'),
        StudentScore(student_id=st1.id, assessment_id=a2.id, score=None, status='absent'),
    ]); s.commit()
    assert recalc_student(s, st1.id) == 50.0


def test_ranking_ties_standard_competition():
    s = db(); classroom, a1, a2, st1, st2, st3 = seed(s)
    for student in (st1, st2):
        s.add_all([
            StudentScore(student_id=student.id, assessment_id=a1.id, score=18, status='entered'),
            StudentScore(student_id=student.id, assessment_id=a2.id, score=45, status='entered'),
        ])
    s.add_all([
        StudentScore(student_id=st3.id, assessment_id=a1.id, score=10, status='entered'),
        StudentScore(student_id=st3.id, assessment_id=a2.id, score=25, status='entered'),
    ]); s.commit()
    assert [x['rank'] for x in class_rankings(s, classroom.id)] == [1, 1, 3]


def test_attendance_is_date_specific_and_saved():
    s = db(); _, _, _, st1, *_ = seed(s)
    s.add_all([
        Attendance(student_id=st1.id, date=date(2026, 9, 9), status='present'),
        Attendance(student_id=st1.id, date=date(2026, 9, 10), status='absent'),
    ]); s.commit()
    x = attendance_summary(s, st1.id)
    assert x['present'] == 1 and x['absent'] == 1 and x['attendance_percent'] == 50.0


def test_mistake_memory_increments():
    s = db(); _, _, _, st1, *_ = seed(s)
    record_mistake(s, st1.id, 'Algebra', 'Formula selection')
    record_mistake(s, st1.id, 'Algebra', 'Formula selection')
    s.commit()
    assert s.query(__import__('app.models', fromlist=['Mistake']).Mistake).first().occurrence_count == 2
