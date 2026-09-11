from fastapi.testclient import TestClient
from app.main import app

def login(c):
    return c.post('/api/auth/login',json={'email':'teacher@example.com','password':'Teacher123!'}).json()['access_token']

def test_offline_sync_is_idempotent_and_persists_attendance_and_score():
    with TestClient(app) as c:
        h={'Authorization':f'Bearer {login(c)}'}
        cl=c.post('/api/classes',headers=h,json={'name':'Offline Sync QA','grade_level':'10'}).json()
        st=c.post('/api/students',headers=h,json={'class_id':cl['id'],'full_name':'Offline Student'}).json()
        su=c.post('/api/subjects',headers=h,json={'name':'Offline Subject'}).json()
        at=c.post('/api/assessment-types',headers=h,json={'name':'Offline Test','max_score':20,'weight':100,'enabled':True,'sort_order':1}).json()
        ass=c.post('/api/assessments',headers=h,json={'assessment_type_id':at['id'],'subject_id':su['id'],'title':'Offline Test 1','date':'2026-09-11','class_id':cl['id']}).json()
        ops=[
          {'operation_id':'offline-att-001','method':'POST','path':'/api/attendance','body':{'student_id':st['id'],'date':'2026-09-11','status':'present'}},
          {'operation_id':'offline-score-001','method':'POST','path':'/api/scores','body':{'student_id':st['id'],'assessment_id':ass['id'],'status':'entered','score':17}},
        ]
        r=c.post('/api/sync',headers=h,json={'operations':ops})
        assert r.status_code==200
        assert [x['status'] for x in r.json()['results']]==['applied','applied']
        r2=c.post('/api/sync',headers=h,json={'operations':ops})
        assert r2.status_code==200
        assert [x['status'] for x in r2.json()['results']]==['already_applied','already_applied']
        rows=c.get(f'/api/attendance?class_id={cl["id"]}&attendance_date=2026-09-11',headers=h).json()['rows']
        assert rows[0]['status']=='present'
        scores=c.get(f'/api/scores?assessment_id={ass["id"]}',headers=h).json()
        assert scores[0]['score']==17
