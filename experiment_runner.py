"""Run repeated experiments against fault profiles and summarize outcomes."""
import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

os.environ.setdefault('TIMEBOX_DB_PATH', '/tmp/timebox_experiment.db')
os.environ.setdefault('TIMEBOX_FIXED_NOW', '2026-04-17T12:00:00')

from app.main import app
from app.db import reset_db
from app.faults import reset_fault_profile


def run_trial(profile=None):
    reset_db()
    reset_fault_profile()
    with TestClient(app) as client:
        client.post('/register', data={'username': 'exp', 'password': 'pass1234'})
        client.post('/login', data={'username': 'exp', 'password': 'pass1234'})
        if profile:
            client.post('/api/fault-profile', json=profile)
        due_at = (datetime.fromisoformat(os.environ['TIMEBOX_FIXED_NOW']) + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
        client.post('/api/tasks', json={'title': 'Alpha Task', 'description': 'demo', 'due_at': due_at})
        data = client.get('/api/tasks?search=alpha').json()
        task_count = len(data['tasks'])
        return {'tasks_seen': task_count, 'counts': data['counts']}


def summarize(trials=5):
    scenarios = {
        'baseline': {},
        'search_bug': {'search_bug': True},
        'duplicate_create_bug': {'duplicate_create_bug': True},
        'dashboard_cache_bug': {'dashboard_cache_bug': True},
    }
    print('Scenario,Observed Task Count,Completed,Due Today,Overdue')
    for name, profile in scenarios.items():
        results = [run_trial(profile) for _ in range(trials)]
        avg_tasks = sum(r['tasks_seen'] for r in results) / trials
        counts = results[-1]['counts']
        print(f"{name},{avg_tasks:.2f},{counts['completed']},{counts['due_today']},{counts['overdue']}")


if __name__ == '__main__':
    summarize()
