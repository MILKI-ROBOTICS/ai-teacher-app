from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def login(client):
    return client.post('/api/auth/login', json={'email':'teacher@example.com','password':'Teacher123!'}).json()['access_token']


def test_student_numbers_follow_alphabetical_order():
    with TestClient(app) as client:
        h={'Authorization':f'Bearer {login(client)}'}
        c=client.post('/api/classes',headers=h,json={'name':'Alphabet QA','grade_level':'10'}).json()
        a=client.post('/api/students',headers=h,json={'class_id':c['id'],'full_name':'Zoe'}).json()
        assert a['student_code']=='1'
        b=client.post('/api/students',headers=h,json={'class_id':c['id'],'full_name':'Abel'}).json()
        assert b['student_code']=='1'
        rows=client.get(f"/api/students?class_id={c['id']}",headers=h).json()
        assert [(r['full_name'], r['student_code']) for r in rows] == [('Abel','1'),('Zoe','2')]


def test_ai_auto_stores_high_confidence_full_exam_and_pass(monkeypatch, tmp_path):
    from app import main as main_module
    from app.schemas import AIGradingOutput
    class FakeGemini:
        def __init__(self): self.enabled=True
        def analyze_answer_sheet(self, image_path, mime_type, questions, answer_key):
            return AIGradingOutput.model_validate({
                'identity': {'name_found': True, 'detected_name':'Auto Store Student', 'detected_code':'1', 'confidence':0.99, 'evidence':'Clear header.'},
                'questions': [
                    {'question_id': q['question_id'], 'student_answer':'correct', 'expected_answer':'correct', 'score':q['maximum_score'], 'maximum_score':q['maximum_score'], 'confidence':0.98, 'reason':'Correct', 'mistake_type':'None', 'topic':q['topic'], 'subtopic':'', 'feedback':'Correct.', 'needs_teacher_review':False}
                    for q in questions
                ],
                'overall_feedback':'Strong performance.'
            })
    monkeypatch.setattr(main_module, 'GeminiService', FakeGemini)
    monkeypatch.setattr(main_module.settings, 'gemini_api_key', 'fake')
    with TestClient(app) as client:
        h={'Authorization':f'Bearer {login(client)}'}
        c=client.post('/api/classes',headers=h,json={'name':'Auto Store','grade_level':'10'}).json()
        s=client.post('/api/subjects',headers=h,json={'name':'Math Auto'}).json()
        t=client.post('/api/assessment-types',headers=h,json={'name':'Final Auto','max_score':100,'weight':100,'enabled':True,'sort_order':1}).json()
        st=client.post('/api/students',headers=h,json={'class_id':c['id'],'full_name':'Auto Store Student'}).json()
        a=client.post('/api/assessments',headers=h,json={'assessment_type_id':t['id'],'subject_id':s['id'],'title':'Final Auto','date':str(date.today()),'class_id':c['id'],'grading_mode':'ai'}).json()
        e=client.post('/api/exams',headers=h,json={'class_id':c['id'],'subject_id':s['id'],'assessment_id':a['id'],'title':'Final Auto Exam','total_marks':10,'answer_key':'Q1 correct Q2 correct'}).json()
        client.post('/api/questions',headers=h,json={'exam_id':e['id'],'question_no':1,'question_text':'Q1','max_score':5,'topic':'Algebra','answer_type':'short_answer'})
        client.post('/api/questions',headers=h,json={'exam_id':e['id'],'question_no':2,'question_text':'Q2','max_score':5,'topic':'Geometry','answer_type':'short_answer'})
        path=Path(tmp_path)/'sheet.jpg'; Image.new('RGB',(1200,1600),'white').save(path)
        with path.open('rb') as f:
            r=client.post(f"/api/exams/{e['id']}/scan",headers=h,files={'upload':('sheet.jpg',f,'image/jpeg')})
        body=r.json(); assert r.status_code==200
        assert body['auto_stored'] is True and body['passed'] is True
        grid=client.get(f"/api/scores?assessment_id={a['id']}",headers=h).json()
        assert grid[0]['score']==100 and grid[0]['status']=='entered'
        profile=client.get(f"/api/students/{st['id']}/profile",headers=h).json()
        assert profile['assessments'][0]['passed'] is True


def test_batch_scan_creates_persistent_job(monkeypatch, tmp_path):
    from app import main as main_module
    monkeypatch.setattr(main_module.settings, 'gemini_api_key', 'fake')
    class FakeGemini:
        def __init__(self): self.enabled=True
        def analyze_answer_sheet(self, image_path, mime_type, questions, answer_key):
            from app.schemas import AIGradingOutput
            return AIGradingOutput.model_validate({'identity': {'name_found':False,'detected_name':None,'detected_code':None,'confidence':0.1,'evidence':'No identity'}, 'questions': [], 'overall_feedback':'Review'})
    monkeypatch.setattr(main_module, 'GeminiService', FakeGemini)
    with TestClient(app) as client:
        h={'Authorization':f'Bearer {login(client)}'}
        c=client.post('/api/classes',headers=h,json={'name':'Batch QA','grade_level':'10'}).json()
        s=client.post('/api/subjects',headers=h,json={'name':'Batch Subject'}).json()
        t=client.post('/api/assessment-types',headers=h,json={'name':'Batch Type','max_score':10,'weight':100,'enabled':True,'sort_order':1}).json()
        a=client.post('/api/assessments',headers=h,json={'assessment_type_id':t['id'],'subject_id':s['id'],'title':'Batch Assessment','date':str(date.today()),'class_id':c['id'],'grading_mode':'ai'}).json()
        e=client.post('/api/exams',headers=h,json={'class_id':c['id'],'subject_id':s['id'],'assessment_id':a['id'],'title':'Batch Exam','total_marks':10,'answer_key':'Q1 correct'}).json()
        client.post('/api/questions',headers=h,json={'exam_id':e['id'],'question_no':1,'question_text':'Q1','max_score':10,'topic':'Test','answer_type':'short_answer'})
        paths=[]
        for i in range(3):
            path=Path(tmp_path)/f'{i}.jpg'; Image.new('RGB',(300,300),'white').save(path); paths.append(path)
        files=[('uploads',(p.name,p.open('rb'),'image/jpeg')) for p in paths]
        try:
            r=client.post(f"/api/exams/{e['id']}/scan-batch",headers=h,files=files)
        finally:
            for _,(_,f,_) in files: f.close()
        assert r.status_code==200
        job=r.json(); status=client.get(f"/api/scan-jobs/{job['job_id']}",headers=h).json()
        assert status['total_files']==3


def test_attendance_reopens_latest_saved_date_and_bulk_and_reports():
    with TestClient(app) as client:
        h={'Authorization':f'Bearer {login(client)}'}
        c=client.post('/api/classes',headers=h,json={'name':'Attendance Persistence','grade_level':'10'}).json()
        s1=client.post('/api/students',headers=h,json={'class_id':c['id'],'full_name':'A Student'}).json()
        s2=client.post('/api/students',headers=h,json={'class_id':c['id'],'full_name':'B Student'}).json()
        for d in ('2026-09-10','2026-09-11'):
            r=client.post('/api/attendance/bulk',headers=h,json={'date':d,'student_ids':[s1['id'],s2['id']],'status':'present'})
            assert r.status_code==200 and r.json()['saved']==2
        latest=client.get(f'/api/attendance/last-date?class_id={c["id"]}',headers=h).json()
        assert latest['latest_date']=='2026-09-11'
        history=client.get(f'/api/attendance/history?class_id={c["id"]}',headers=h).json()
        assert history['dates'][:2]==['2026-09-11','2026-09-10']
        attendance=client.get(f'/api/attendance?class_id={c["id"]}&attendance_date=2026-09-10',headers=h).json()
        assert all(r['recorded'] for r in attendance['rows'])
        overview=client.get(f'/api/reports/student/{s1["id"]}?report_type=attendance',headers=h)
        assert overview.status_code==200 and overview.json()['summary']['present']==2
        csv=client.get(f'/api/reports/student/{s1["id"]}/csv?report_type=score',headers=h)
        assert csv.status_code==200 and 'assessment' in csv.text


def test_login_cookie_and_security_headers():
    with TestClient(app) as client:
        r=client.post('/api/auth/login',json={'email':'teacher@example.com','password':'Teacher123!'})
        assert r.status_code==200
        assert any('HttpOnly' in c for c in [r.headers.get('set-cookie','')])
        assert r.headers.get('x-content-type-options')=='nosniff'
        assert r.headers.get('x-frame-options')=='DENY'
        me=client.get('/api/me')
        assert me.status_code==200
