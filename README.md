# TimeBox Testing Lab

TimeBox Testing Lab is a master’s-level software testing project built to evaluate how real bug classes and unstable runtime conditions affect automated tests. Instead of only testing normal CRUD flows, this project includes **fault injection profiles** that intentionally introduce regressions and flaky behavior.

## What makes this a stronger testing project
- controlled **fault injection** instead of a plain demo app
- API, UI, negative, and experiment-driven testing
- reproducible scenarios for duplicate submissions, search regressions, sorting instability, dashboard stale state, and boundary-time failures
- visible browser demo for class presentations
- deployment-ready configuration for free cloud hosting

## Fault profiles
The app can enable these fault modes through `/api/fault-profile`:
- `slow_ui`
- `duplicate_create_bug`
- `unstable_sort_bug`
- `search_bug`
- `dashboard_cache_bug`
- `midnight_boundary`

The dashboard also includes a session-based fault control panel, so you can toggle bugs on and off from the browser without affecting other users.
It also includes one-click demo presets for search, timing, and sorting scenarios.

## Project structure
```text
app/
  main.py
  db.py
  faults.py
  templates/
  static/
tests/
  test_api.py
  test_ui_playwright.py
demo_browser_run.py
experiment_runner.py
requirements.txt
render.yaml
Procfile
```

## Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
```

## Run the app
```bash
uvicorn app.main:app --reload
```
Then open `http://127.0.0.1:8000`.

## Run tests
```bash
PYTHONPATH=. pytest -v
```

## Run the visible demo
```bash
python demo_browser_run.py
```
This launches a real Chromium browser and walks through multiple scenarios one by one, including browser-side fault toggles.

## Run experiments
```bash
python experiment_runner.py
```
This prints scenario-level outcomes that you can reference in your final report.

## Deployment
This repo includes `render.yaml` and a `Procfile` so you can deploy quickly to Render.

## Suggested presentation angle
Describe the project as a **fault-injection testing lab** that studies how automated tests behave when known bug patterns are activated. That frames the work as a testing and experimentation project, not just a basic task manager.


## Quick Start

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install
```

Start the app and open the browser automatically:

```bash
python run_app.py
```

If you prefer the manual server command, use the virtual-environment copy of Uvicorn:

```bash
python -m uvicorn app.main:app --reload
```
# timebox-testing-lab
