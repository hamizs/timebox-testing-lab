"""Visible end-to-end demo runner for TimeBox Testing Lab."""
import os
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent


def free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for_server(base_url, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(base_url + '/api/health', timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError('Server did not start in time')


def step(label):
    print(f'\n[DEMO] {label}')


def capture_demo_screenshot(page, path):
    page.wait_for_load_state('networkidle')
    page.evaluate('window.scrollTo({ top: 0, behavior: "instant" })')
    page.wait_for_timeout(350)
    page.screenshot(path=str(path), full_page=True)


def main():
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    env = os.environ.copy()
    env['TIMEBOX_DB_PATH'] = f'/tmp/timebox_demo_{port}.db'
    env['TIMEBOX_FIXED_NOW'] = '2026-04-17T12:00:00'
    process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', str(port)],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    try:
        wait_for_server(base)
        requests.post(base + '/api/reset', timeout=3)
        with sync_playwright() as p:
            scenarios = [
                ('Happy Path', None, ()),
                ('Duplicate Create Bug', None, ('duplicate_create_bug',)),
                ('Search Demo Preset', 'search_demo', ()),
                ('Timing Demo Preset', 'timing_demo', ()),
                ('Sorting Demo Preset', 'sorting_demo', ()),
            ]
            for idx, (name, preset_name, profile) in enumerate(scenarios, start=1):
                requests.post(base + '/api/reset', timeout=3)
                step(f'Scenario {idx}: {name}')
                browser = p.chromium.launch(headless=False, slow_mo=350)
                page = browser.new_page(viewport={'width': 1600, 'height': 1200})
                username = f'user{idx}'
                page.goto(base + '/register')
                page.get_by_test_id('register-username').fill(username)
                page.get_by_test_id('register-password').fill('pass1234')
                page.get_by_test_id('register-submit').click()
                page.goto(base + '/login')
                page.get_by_test_id('login-username').fill(username)
                page.get_by_test_id('login-password').fill('pass1234')
                page.get_by_test_id('login-submit').click()
                if preset_name:
                    page.get_by_test_id(f'preset-apply-{preset_name}').click()
                for fault_name in profile:
                    page.get_by_test_id(f'fault-toggle-{fault_name}').click()
                if preset_name or profile:
                    expect(page.get_by_test_id('fault-active-banner')).to_be_visible()
                for title, due in [('Write tests', '2026-04-17T15:00'), ('Alpha bug repro', '2026-04-16T11:00')]:
                    page.get_by_test_id('task-title').fill(title)
                    page.get_by_test_id('task-description').fill('Automated demo task')
                    page.get_by_test_id('task-due-at').fill(due)
                    page.get_by_test_id('create-task-submit').click()
                    page.wait_for_timeout(500)
                page.get_by_test_id('search-input').fill('alpha')
                page.get_by_test_id('apply-controls').click()
                page.wait_for_timeout(1200)
                if page.locator('[data-testid="task-row"]').count() > 0:
                    page.locator('[data-testid^="toggle-task-"]').first.click()
                    page.wait_for_timeout(700)
                capture_demo_screenshot(page, PROJECT_ROOT / f'demo_scenario_{idx}.png')
                browser.close()
        print('\n[DEMO] All scenarios completed successfully.')
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
