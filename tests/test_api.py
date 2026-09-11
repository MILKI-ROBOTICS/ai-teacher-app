import os
from pathlib import Path
Path('test_api.db').unlink(missing_ok=True)
os.environ['DATABASE_URL']='sqlite:///./test_api.db'
os.environ['SECRET_KEY']='test-secret-which-is-at-least-32-bytes-long'


from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get('/api/health')
        assert r.status_code == 200 and r.json()['status'] == 'ok'


def login(client):
    r = client.post('/api/auth/login', json={'email': 'teacher@example.com', 'password': 'Teacher123!'})
    assert r.status_code == 200
    return r.json()['access_token']


def test_login_and_initial_workspace_is_empty():
    with TestClient(app) as client:
        token = login(client); headers = {'Authorization': f'Bearer {token}'}
        assert client.get('/api/students', headers=headers).json() == []
        assert client.get('/api/classes', headers=headers).json() == []
        assert client.get('/api/assessment-types', headers=headers).json() == []


def test_create_class_student_subject_and_score_flow():
    with TestClient(app) as client:
        token = login(client); headers = {'Authorization': f'Bearer {token}'}
        cls = client.post('/api/classes', headers=headers, json={'name':'11A','grade_level':'11'}).json()
        subj = client.post('/api/subjects', headers=headers, json={'name':'Physics'}).json()
        typ = client.post('/api/assessment-types', headers=headers, json={'name':'Test','max_score':20,'weight':100,'enabled':True,'sort_order':1}).json()
        student = client.post('/api/students', headers=headers, json={'class_id':cls['id'],'student_code':'ST001','full_name':'Abdi Bekele'}).json()
        assessment = client.post('/api/assessments', headers=headers, json={'assessment_type_id':typ['id'],'subject_id':subj['id'],'title':'Test 1','date':'2026-09-10','class_id':cls['id']}).json()
        score = client.post('/api/scores', headers=headers, json={'student_id':student['id'],'assessment_id':assessment['id'],'status':'entered','score':17}).json()
        assert score['student_average'] == 85.0


def test_score_validation_prevents_over_max():
    with TestClient(app) as client:
        token = login(client); headers={'Authorization':f'Bearer {token}'}
        cls=client.post('/api/classes',headers=headers,json={'name':'11B','grade_level':'11'}).json()
        sub=client.post('/api/subjects',headers=headers,json={'name':'Chemistry'}).json()
        typ=client.post('/api/assessment-types',headers=headers,json={'name':'Quiz','max_score':10,'weight':100,'enabled':True,'sort_order':1}).json()
        st=client.post('/api/students',headers=headers,json={'class_id':cls['id'],'student_code':'ST002','full_name':'Lensa Test'}).json()
        ass=client.post('/api/assessments',headers=headers,json={'assessment_type_id':typ['id'],'subject_id':sub['id'],'title':'Q1','date':'2026-09-10','class_id':cls['id']}).json()
        r=client.post('/api/scores',headers=headers,json={'student_id':st['id'],'assessment_id':ass['id'],'status':'entered','score':99})
        assert r.status_code == 400



def test_scan_uses_ai_identity_instead_of_manual_student_selection(monkeypatch, tmp_path):
    from PIL import Image
    from app import main as main_module
    from app.schemas import AIGradingOutput

    class FakeGemini:
        def __init__(self):
            self.enabled = True
        def analyze_answer_sheet(self, image_path, mime_type, questions, answer_key):
            return AIGradingOutput.model_validate({
                'identity': {
                    'name_found': True,
                    'detected_name': 'Abdi Bekele',
                    'detected_code': 'ST001',
                    'confidence': 0.97,
                    'evidence': 'Header name read clearly.'
                },
                'questions': [{
                    'question_id': questions[0]['question_id'], 'student_answer': 'x=5', 'expected_answer': 'x=5',
                    'score': questions[0]['maximum_score'], 'maximum_score': questions[0]['maximum_score'],
                    'confidence': 0.96, 'reason': 'Correct', 'mistake_type': 'None',
                    'topic': questions[0]['topic'], 'subtopic': '', 'feedback': 'Correct.', 'needs_teacher_review': False
                }],
                'overall_feedback': 'Correct.'
            })

    monkeypatch.setattr(main_module, 'GeminiService', FakeGemini)
    monkeypatch.setattr(main_module.settings, 'gemini_api_key', 'fake-key')
    with TestClient(app) as client:
        token=login(client); headers={'Authorization':f'Bearer {token}'}
        cls=client.post('/api/classes',headers=headers,json={'name':'AIClass','grade_level':'10'}).json()
        sub=client.post('/api/subjects',headers=headers,json={'name':'Biology'}).json()
        typ=client.post('/api/assessment-types',headers=headers,json={'name':'Final','max_score':10,'weight':100,'enabled':True,'sort_order':1}).json()
        st=client.post('/api/students',headers=headers,json={'class_id':cls['id'],'student_code':'ST001','full_name':'Abdi Bekele'}).json()
        ass=client.post('/api/assessments',headers=headers,json={'assessment_type_id':typ['id'],'subject_id':sub['id'],'title':'Final Bio','date':'2026-09-10','class_id':cls['id'],'grading_mode':'ai'}).json()
        exam=client.post('/api/exams',headers=headers,json={'class_id':cls['id'],'subject_id':sub['id'],'assessment_id':ass['id'],'title':'Bio Exam','total_marks':5,'answer_key':'Q1=x=5'}).json()
        q=client.post('/api/questions',headers=headers,json={'exam_id':exam['id'],'question_no':1,'question_text':'Solve 2x+5=15','max_score':5,'topic':'Algebra','answer_type':'mathematics'}).json()
        image_path=tmp_path/'sheet.jpg'; Image.new('RGB',(1200,1600),'white').save(image_path)
        with image_path.open('rb') as f:
            response=client.post(f"/api/exams/{exam['id']}/scan",headers=headers,files={'upload':('sheet.jpg',f,'image/jpeg')})
        body=response.json()
        assert response.status_code==200
        assert body['identity']['matched_student']['id']==st['id']
        assert body['ai_results'][0]['ai_result_id'] is not None
        details=client.get(f"/api/submissions/{body['submission_id']}",headers=headers).json()
        assert details['student']['id']==st['id']
