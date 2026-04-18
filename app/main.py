from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .auth import SESSION_KEY, current_user
from .db import get_conn, init_db, reset_db
from .faults import (
    active_fault_names,
    apply_fault_preset,
    fault_cards,
    get_cached_dashboard,
    get_fault_profile,
    preset_cards,
    profile_dict,
    reset_fault_profile,
    set_cached_dashboard,
    set_fault_profile,
    toggle_fault,
)

app = FastAPI(title='TimeBox Testing Lab')
app.add_middleware(SessionMiddleware, secret_key=os.getenv('TIMEBOX_SECRET', 'dev-secret-key'))

BASE_DIR = Path(__file__).resolve().parent
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))


def now() -> datetime:
    value = os.getenv('TIMEBOX_FIXED_NOW')
    if value:
        return datetime.fromisoformat(value)
    return datetime.now()


def normalize_due_at(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime('%Y-%m-%dT%H:%M')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid due date') from exc


def format_due_display(value: str) -> str:
    return datetime.fromisoformat(value).strftime('%b %d, %Y · %I:%M %p')


def maybe_delay(profile) -> None:
    if profile.slow_ui:
        time.sleep(0.35)


def task_status(row, profile=None) -> str:
    active_profile = profile or get_fault_profile()
    if row['completed']:
        return 'Completed'
    due = datetime.fromisoformat(row['due_at'])
    current = now()
    if active_profile.midnight_boundary:
        current = current + timedelta(minutes=2)
    if due < current:
        return 'Overdue'
    if due.date() == current.date():
        return 'Due Today'
    return 'Active'


def task_to_item(row, profile) -> dict[str, Any]:
    item = dict(row)
    item['completed'] = bool(item['completed'])
    item['status'] = task_status(row, profile)
    item['due_display'] = format_due_display(row['due_at'])
    item['due_input'] = normalize_due_at(row['due_at'])
    item['is_overdue'] = item['status'] == 'Overdue'
    return item


def get_task_for_user(user_id: int, task_id: int, request: Request) -> dict[str, Any] | None:
    profile = get_fault_profile(request)
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id)).fetchone()
    if row is None:
        return None
    return task_to_item(row, profile)


def dashboard_counts(user_id: int, request: Request):
    profile = get_fault_profile(request)
    if profile.dashboard_cache_bug and get_cached_dashboard(request) is not None:
        return get_cached_dashboard(request)
    with get_conn() as conn:
        rows = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,)).fetchall()
    counts = {'due_today': 0, 'overdue': 0, 'completed': 0}
    for row in rows:
        status = task_status(row, profile)
        if status == 'Due Today':
            counts['due_today'] += 1
        elif status == 'Overdue':
            counts['overdue'] += 1
        elif status == 'Completed':
            counts['completed'] += 1
    if profile.dashboard_cache_bug:
        set_cached_dashboard(request.session, counts)
    return counts


def fetch_tasks(
    user_id: int,
    request: Request,
    search: str = '',
    filter_by: str = 'all',
    sort_by: str = 'created_desc',
):
    profile = get_fault_profile(request)
    with get_conn() as conn:
        rows = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,)).fetchall()
    items = [task_to_item(row, profile) for row in rows]

    if search:
        if profile.search_bug:
            items = [t for t in items if search in t['title']]
        else:
            search_lower = search.lower()
            items = [t for t in items if search_lower in t['title'].lower()]

    if filter_by != 'all':
        mapping = {
            'active': 'Active',
            'completed': 'Completed',
            'overdue': 'Overdue',
            'due_today': 'Due Today',
        }
        status = mapping.get(filter_by)
        if status:
            items = [t for t in items if t['status'] == status]

    if sort_by == 'due_asc':
        items.sort(key=lambda t: (t['due_at'], t['title']))
    elif sort_by == 'title_asc':
        items.sort(key=lambda t: t['title'].lower())
    else:
        if profile.unstable_sort_bug:
            items.sort(key=lambda t: t['due_at'])
        else:
            items.sort(key=lambda t: (t['created_at'], t['id']), reverse=True)
    return items


@app.on_event('startup')
def startup():
    init_db()


@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    profile = get_fault_profile(request)
    maybe_delay(profile)
    search = request.query_params.get('search', '')
    filter_by = request.query_params.get('filter', 'all')
    sort_by = request.query_params.get('sort', 'created_desc')
    edit_task = None
    edit_task_id = request.query_params.get('edit_task_id', '').strip()
    if edit_task_id.isdigit():
        edit_task = get_task_for_user(user['id'], int(edit_task_id), request)
    tasks = fetch_tasks(
        user['id'],
        request,
        search=search,
        filter_by=filter_by,
        sort_by=sort_by,
    )
    return templates.TemplateResponse(
        request,
        'dashboard.html',
        {
            'request': request,
            'user': user,
            'tasks': tasks,
            'counts': dashboard_counts(user['id'], request),
            'faults': profile_dict(profile),
            'fault_cards': fault_cards(profile),
            'preset_cards': preset_cards(),
            'active_faults': active_fault_names(profile),
            'search': search,
            'filter_by': filter_by,
            'sort_by': sort_by,
            'editor_task': edit_task,
        },
    )


@app.get('/register', response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, 'register.html', {'request': request, 'error': ''})


@app.post('/register')
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    if len(password) < 4:
        return templates.TemplateResponse(
            request,
            'register.html',
            {'request': request, 'error': 'Password must be at least 4 characters.'},
            status_code=400,
        )
    try:
        with get_conn() as conn:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
    except Exception:
        return templates.TemplateResponse(
            request,
            'register.html',
            {'request': request, 'error': 'Username already exists.'},
            status_code=400,
        )
    return RedirectResponse('/login', status_code=302)


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, 'login.html', {'request': request, 'error': ''})


@app.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with get_conn() as conn:
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
    if not user:
        return templates.TemplateResponse(
            request,
            'login.html',
            {'request': request, 'error': 'Invalid username or password.'},
            status_code=400,
        )

    request.session[SESSION_KEY] = user['id']
    return RedirectResponse('/', status_code=302)


@app.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=302)


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user


@app.post('/faults/{fault_name}/toggle')
def toggle_fault_from_dashboard(fault_name: str, request: Request):
    require_user(request)
    try:
        toggle_fault(request.session, fault_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Unknown fault profile') from exc
    return RedirectResponse('/', status_code=302)


@app.post('/faults/reset')
def reset_faults_from_dashboard(request: Request):
    require_user(request)
    reset_fault_profile(request.session)
    return RedirectResponse('/', status_code=302)


@app.post('/fault-presets/{preset_name}')
def apply_fault_preset_from_dashboard(preset_name: str, request: Request):
    require_user(request)
    try:
        apply_fault_preset(request.session, preset_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Unknown fault preset') from exc
    return RedirectResponse('/', status_code=302)


@app.post('/tasks')
def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(''),
    due_at: str = Form(...),
):
    user = require_user(request)
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail='Title is required')
    due_value = normalize_due_at(due_at)
    created = now().isoformat(timespec='seconds')
    profile = get_fault_profile(request)
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO tasks (user_id, title, description, due_at, completed, created_at) VALUES (?, ?, ?, ?, 0, ?)',
            (user['id'], title, description.strip(), due_value, created),
        )
        if profile.duplicate_create_bug:
            conn.execute(
                'INSERT INTO tasks (user_id, title, description, due_at, completed, created_at) VALUES (?, ?, ?, ?, 0, ?)',
                (user['id'], title, description.strip(), due_value, created),
            )
        conn.commit()
    return RedirectResponse('/', status_code=302)


@app.post('/tasks/{task_id}/edit')
def edit_task(
    task_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(''),
    due_at: str = Form(...),
):
    user = require_user(request)
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail='Title is required')
    due_value = normalize_due_at(due_at)
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Task not found')
        conn.execute(
            'UPDATE tasks SET title = ?, description = ?, due_at = ? WHERE id = ? AND user_id = ?',
            (title, description.strip(), due_value, task_id, user['id']),
        )
        conn.commit()
    return RedirectResponse('/', status_code=302)


@app.post('/tasks/{task_id}/toggle')
def toggle_task(task_id: int, request: Request):
    user = require_user(request)
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Task not found')
        new_val = 0 if row['completed'] else 1
        conn.execute('UPDATE tasks SET completed = ? WHERE id = ?', (new_val, task_id))
        conn.commit()
    return RedirectResponse('/', status_code=302)


@app.post('/tasks/{task_id}/delete')
def delete_task(task_id: int, request: Request):
    user = require_user(request)
    with get_conn() as conn:
        conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user['id']))
        conn.commit()
    return RedirectResponse('/', status_code=302)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/favicon.ico')
def favicon():
    return JSONResponse({'status': 'ok'})


@app.get('/api/fault-profile')
def api_get_fault_profile(request: Request):
    return profile_dict(request)


@app.post('/api/fault-profile')
def api_set_fault_profile(request: Request, payload: dict):
    return profile_dict(set_fault_profile(request.session, **payload))


@app.post('/api/reset')
def api_reset(request: Request):
    reset_fault_profile(request.session)
    reset_db()
    return {'status': 'reset'}


@app.get('/api/tasks')
def api_tasks(request: Request, search: str = '', filter: str = 'all', sort: str = 'created_desc'):
    user = require_user(request)
    return {'tasks': fetch_tasks(user['id'], request, search, filter, sort), 'counts': dashboard_counts(user['id'], request)}


@app.post('/api/tasks')
def api_create_task(request: Request, payload: dict):
    user = require_user(request)
    title = (payload.get('title') or '').strip()
    if not title:
        raise HTTPException(status_code=400, detail='Title is required')
    due_at = payload.get('due_at')
    if not due_at:
        raise HTTPException(status_code=400, detail='due_at is required')
    due_value = normalize_due_at(due_at)
    created = now().isoformat(timespec='seconds')
    profile = get_fault_profile(request)
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO tasks (user_id, title, description, due_at, completed, created_at) VALUES (?, ?, ?, ?, 0, ?)',
            (user['id'], title, payload.get('description', ''), due_value, created),
        )
        if profile.duplicate_create_bug:
            conn.execute(
                'INSERT INTO tasks (user_id, title, description, due_at, completed, created_at) VALUES (?, ?, ?, ?, 0, ?)',
                (user['id'], title, payload.get('description', ''), due_value, created),
            )
        conn.commit()
    return {'status': 'created'}


@app.put('/api/tasks/{task_id}')
def api_update_task(request: Request, task_id: int, payload: dict):
    user = require_user(request)
    title = (payload.get('title') or '').strip()
    if not title:
        raise HTTPException(status_code=400, detail='Title is required')
    due_at = payload.get('due_at')
    if not due_at:
        raise HTTPException(status_code=400, detail='due_at is required')
    due_value = normalize_due_at(due_at)
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Task not found')
        completed = bool(payload.get('completed', row['completed']))
        conn.execute(
            'UPDATE tasks SET title = ?, description = ?, due_at = ?, completed = ? WHERE id = ? AND user_id = ?',
            (title, payload.get('description', ''), due_value, int(completed), task_id, user['id']),
        )
        conn.commit()
    updated = get_task_for_user(user['id'], task_id, request)
    if updated is None:
        raise HTTPException(status_code=404, detail='Task not found')
    return {'task': updated}
