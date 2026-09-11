import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_hardening.db')
os.environ.setdefault('SECRET_KEY', 'test-secret-which-is-at-least-32-bytes-long')

from fastapi.testclient import TestClient
from app.main import app


def login(client):
    return client.post('/api/auth/login', json={'email':'teacher@example.com','password':'Teacher123!'}).json()['access_token']


def test_zero_status_forces_zero_score():
    with TestClient(app) as client:
        h={'Authorization':f'Bearer {login(client)}'}
        c=client.post('/api/classes',headers=h,json={'name':'Hardening A','grade_level':'11'}).json()
        s=client.post('/api/subjects',headers=h,json={'name':'Hardening Math'}).json()
        t=client.post('/api/assessment-types',headers=h,json={'name':'Quiz H','max_score':10,'weight':100,'enabled':True,'sort_order':1}).json()
        st=client.post('/api/students',headers=h,json={'class_id':c['id'],'student_code':'HZ1','full_name':'Hardening Student'}).json()
        a=client.post('/api/assessments',headers=h,json={'assessment_type_id':t['id'],'subject_id':s['id'],'title':'Zero Test','date':'2026-09-11','class_id':c['id']}).json()
        r=client.post('/api/scores',headers=h,json={'student_id':st['id'],'assessment_id':a['id'],'status':'zero','score':9})
        assert r.status_code==200
        grid=client.get(f"/api/scores?assessment_id={a['id']}",headers=h).json()
        assert grid[0]['score']==0 and grid[0]['status']=='zero'


def test_duplicate_class_is_rejected():
    with TestClient(app) as client:
        h={'Authorization':f'Bearer {login(client)}'}
        payload={'name':'Duplicate Class','grade_level':'10'}
        assert client.post('/api/classes',headers=h,json=payload).status_code==200
        assert client.post('/api/classes',headers=h,json=payload).status_code==409
