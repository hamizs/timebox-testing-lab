import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ['TIMEBOX_DB_PATH'] = '/tmp/timebox_test_api.db'
os.environ['TIMEBOX_FIXED_NOW'] = '2026-04-17T12:00:00'

from app.main import app
from app.db import reset_db
from app.faults import reset_fault_profile


@pytest.fixture()
def client():
    reset_db()
    reset_fault_profile()
    with TestClient(app) as c:
        yield c


def register_and_login(client, username='alice', password='pass1234'):
    client.post('/register', data={'username': username, 'password': password})
    client.post('/login', data={'username': username, 'password': password})


def create_task(client, title='Task A', hours=2):
    due_at = (datetime.fromisoformat(os.environ['TIMEBOX_FIXED_NOW']) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M')
    return client.post('/api/tasks', json={'title': title, 'description': 'desc', 'due_at': due_at})


def test_register_login_and_create_task(client):
    register_and_login(client)
    response = create_task(client, 'Write report')
    assert response.status_code == 200
    tasks = client.get('/api/tasks').json()['tasks']
    assert len(tasks) == 1
    assert tasks[0]['title'] == 'Write report'


def test_update_task_via_api(client):
    register_and_login(client)
    create_task(client, 'Draft report')
    task = client.get('/api/tasks').json()['tasks'][0]
    response = client.put(
        f"/api/tasks/{task['id']}",
        json={
            'title': 'Final report',
            'description': 'edited',
            'due_at': '2026-04-17T18:00',
            'completed': True,
        },
    )
    assert response.status_code == 200
    updated = response.json()['task']
    assert updated['title'] == 'Final report'
    assert updated['description'] == 'edited'
    assert updated['completed'] is True


def test_unauthorized_api_access_blocked(client):
    response = client.get('/api/tasks')
    assert response.status_code == 401


def test_empty_title_rejected(client):
    register_and_login(client)
    response = client.post('/api/tasks', json={'title': '   ', 'due_at': '2026-04-17T15:00'})
    assert response.status_code == 400


def test_duplicate_create_fault_profile(client):
    register_and_login(client)
    client.post('/api/fault-profile', json={'duplicate_create_bug': True})
    create_task(client, 'Duplicate Risk')
    tasks = client.get('/api/tasks').json()['tasks']
    assert len(tasks) == 2


def test_search_bug_profile_is_case_sensitive(client):
    register_and_login(client)
    create_task(client, 'Alpha Task')
    client.post('/api/fault-profile', json={'search_bug': True})
    tasks = client.get('/api/tasks?search=alpha').json()['tasks']
    assert tasks == []


def test_midnight_boundary_fault_changes_status(client):
    register_and_login(client)
    create_task(client, 'Boundary Task', hours=0)
    client.post('/api/fault-profile', json={'midnight_boundary': True})
    tasks = client.get('/api/tasks').json()['tasks']
    assert tasks[0]['status'] in {'Overdue', 'Due Today'}


def test_fault_profiles_are_isolated_per_session():
    reset_db()
    with TestClient(app) as client_a, TestClient(app) as client_b:
        client_a.post('/register', data={'username': 'session_a', 'password': 'pass1234'})
        client_a.post('/login', data={'username': 'session_a', 'password': 'pass1234'})
        client_b.post('/register', data={'username': 'session_b', 'password': 'pass1234'})
        client_b.post('/login', data={'username': 'session_b', 'password': 'pass1234'})

        client_a.post('/api/fault-profile', json={'duplicate_create_bug': True})

        profile_a = client_a.get('/api/fault-profile').json()
        profile_b = client_b.get('/api/fault-profile').json()

        assert profile_a['duplicate_create_bug'] is True
        assert profile_b['duplicate_create_bug'] is False


def test_fault_preset_replaces_session_profile(client):
    register_and_login(client)
    client.post('/api/fault-profile', json={'duplicate_create_bug': True, 'dashboard_cache_bug': True})

    response = client.post('/fault-presets/timing_demo', follow_redirects=False)
    assert response.status_code == 302

    profile = client.get('/api/fault-profile').json()
    assert profile['slow_ui'] is True
    assert profile['midnight_boundary'] is True
    assert profile['duplicate_create_bug'] is False
    assert profile['dashboard_cache_bug'] is False
