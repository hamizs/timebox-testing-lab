import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ['TIMEBOX_FIXED_NOW'] = '2026-04-17T12:00:00'


def free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='module')
def live_server():
    port = free_port()
    env = os.environ.copy()
    env['TIMEBOX_DB_PATH'] = f'/tmp/timebox_ui_{port}.db'
    process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', str(port)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f'http://127.0.0.1:{port}'
    for _ in range(50):
        try:
            import urllib.request
            urllib.request.urlopen(base + '/login', timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield base
    process.terminate()
    process.wait(timeout=10)


def register(page, base, username='demo', password='pass1234'):
    page.goto(base + '/register')
    page.get_by_test_id('register-username').fill(username)
    page.get_by_test_id('register-password').fill(password)
    page.get_by_test_id('register-submit').click()


def login(page, base, username='demo', password='pass1234'):
    page.goto(base + '/login')
    page.get_by_test_id('login-username').fill(username)
    page.get_by_test_id('login-password').fill(password)
    page.get_by_test_id('login-submit').click()


def test_end_to_end_happy_path(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        register(page, live_server)
        login(page, live_server)
        page.get_by_test_id('fault-reset').click()
        page.get_by_test_id('task-title').fill('UI Task')
        page.get_by_test_id('task-due-at').fill('2026-04-17T15:00')
        page.get_by_test_id('create-task-submit').click()
        page.get_by_text('UI Task').wait_for()
        page.get_by_test_id('search-input').fill('UI')
        page.get_by_test_id('apply-controls').click()
        page.get_by_text('UI Task').wait_for()
        browser.close()


def test_edit_existing_task(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        register(page, live_server, 'editor', 'pass1234')
        login(page, live_server, 'editor', 'pass1234')
        page.get_by_test_id('task-title').fill('Original Task')
        page.get_by_test_id('task-description').fill('before edit')
        page.get_by_test_id('task-due-at').fill('2026-04-17T15:30')
        page.get_by_test_id('create-task-submit').click()
        page.get_by_text('Original Task').wait_for()
        page.locator('[data-testid="task-row"]').filter(has_text='Original Task').get_by_role('link', name='Edit').click()
        page.get_by_test_id('task-title').fill('Edited Task')
        page.get_by_test_id('task-description').fill('after edit')
        page.get_by_test_id('task-due-at').fill('2026-04-17T18:45')
        page.get_by_test_id('create-task-submit').click()
        page.get_by_text('Edited Task').wait_for()
        assert page.locator('text=Original Task').count() == 0
        assert page.locator('text=after edit').count() >= 1
        browser.close()


def test_fault_profile_duplicate_bug_visible(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        register(page, live_server, 'faulty', 'pass1234')
        login(page, live_server, 'faulty', 'pass1234')
        page.get_by_test_id('fault-toggle-duplicate_create_bug').click()
        page.get_by_test_id('fault-active-banner').wait_for()
        page.get_by_test_id('task-title').fill('Dup Task')
        page.get_by_test_id('task-due-at').fill('2026-04-17T16:00')
        page.get_by_test_id('create-task-submit').click()
        rows = page.locator('[data-testid="task-row"]')
        expect_count = rows.count()
        assert expect_count >= 2
        browser.close()


def test_demo_preset_applies_session_faults(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        register(page, live_server, 'preset_user', 'pass1234')
        login(page, live_server, 'preset_user', 'pass1234')
        page.get_by_test_id('preset-apply-search_demo').click()
        page.get_by_test_id('fault-active-banner').wait_for()
        banner_text = page.get_by_test_id('fault-active-banner').text_content() or ''
        assert 'search_bug' in banner_text
        page.get_by_test_id('task-title').fill('Alpha Task')
        page.get_by_test_id('task-due-at').fill('2026-04-17T17:00')
        page.get_by_test_id('create-task-submit').click()
        page.get_by_test_id('search-input').fill('alpha')
        page.get_by_test_id('apply-controls').click()
        assert page.locator('[data-testid="task-row"]').count() == 0
        browser.close()
