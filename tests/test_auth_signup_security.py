import os
os.environ.setdefault('SECRET_KEY', 'test-secret-which-is-at-least-32-bytes-long')

from fastapi.testclient import TestClient
from app.main import app
from app.security import create_token


def test_signup_creates_isolated_workspace_and_sets_session():
    with TestClient(app) as client:
        email='newteacher+qa@example.com'
        client.post('/api/auth/logout')
        r=client.post('/api/auth/signup', json={
            'email': email,
            'full_name':'New Teacher',
            'school_name':'QA School',
            'password':'StrongPass1234',
            'password_confirm':'StrongPass1234',
        })
        assert r.status_code==200, r.text
        assert r.cookies.get('ati_session')
        assert r.cookies.get('ati_csrf')
        assert client.get('/api/me').status_code==200
        assert client.get('/api/classes').json()==[]


def test_signup_rejects_duplicate_email():
    with TestClient(app) as client:
        r=client.post('/api/auth/signup', json={
            'email':'teacher@example.com',
            'full_name':'Another Teacher',
            'school_name':'Other School',
            'password':'StrongPass1234',
            'password_confirm':'StrongPass1234',
        })
        assert r.status_code==409


def test_cookie_mutation_requires_csrf_header():
    with TestClient(app) as client:
        r=client.post('/api/auth/login', json={'email':'teacher@example.com','password':'Teacher123!'})
        assert r.status_code==200
        without_csrf=client.post('/api/classes', json={'name':'CSRF Block','grade_level':'10'})
        assert without_csrf.status_code==403
        csrf=client.cookies.get('ati_csrf')
        ok=client.post('/api/classes', headers={'X-CSRF-Token':csrf}, json={'name':'CSRF Allowed','grade_level':'10'})
        assert ok.status_code==200


def test_logout_invalidates_old_bearer_token():
    with TestClient(app) as client:
        r=client.post('/api/auth/login', json={'email':'teacher@example.com','password':'Teacher123!'})
        token=r.json()['access_token']
        assert client.post('/api/auth/logout', headers={'X-CSRF-Token':client.cookies.get('ati_csrf')}).status_code==200
        me=client.get('/api/me', headers={'Authorization':f'Bearer {token}'})
        assert me.status_code==401


def test_ui_no_custom_install_or_localstorage_token():
    from pathlib import Path
    html=Path('app/templates/index.html').read_text()
    js=Path('app/static/app.js').read_text()
    assert 'id="install-app"' not in html
    assert 'beforeinstallprompt' not in js
    assert 'localStorage' not in js
