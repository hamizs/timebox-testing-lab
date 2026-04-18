from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, MutableMapping

PROFILE_SESSION_KEY = 'fault_profile'
DASHBOARD_CACHE_KEY = 'fault_dashboard_cache'

FAULT_LABELS = {
    'slow_ui': 'Slow UI',
    'duplicate_create_bug': 'Duplicate Create',
    'unstable_sort_bug': 'Unstable Sort',
    'search_bug': 'Search Regression',
    'dashboard_cache_bug': 'Dashboard Cache',
    'midnight_boundary': 'Midnight Boundary',
}

FAULT_DESCRIPTIONS = {
    'slow_ui': 'Adds extra UI delay to simulate sluggish rendering and timing-sensitive tests.',
    'duplicate_create_bug': 'Creates the same task twice so duplicate-submission bugs become visible.',
    'unstable_sort_bug': 'Removes the stable secondary sort key so ordering can shift unexpectedly.',
    'search_bug': 'Makes search case-sensitive so realistic search regressions show up quickly.',
    'dashboard_cache_bug': 'Reuses stale dashboard counts inside the active browser session.',
    'midnight_boundary': 'Pushes the effective time forward to expose due-date boundary problems.',
}

PRESET_DEFINITIONS = {
    'search_demo': {
        'label': 'Search Demo',
        'description': 'Turns on the search regression so a normal search flow visibly breaks.',
        'faults': ('search_bug',),
    },
    'timing_demo': {
        'label': 'Timing Demo',
        'description': 'Combines UI delay and boundary-time behavior for timing-sensitive demonstrations.',
        'faults': ('slow_ui', 'midnight_boundary'),
    },
    'sorting_demo': {
        'label': 'Sorting Demo',
        'description': 'Activates unstable ordering so list position can shift between runs.',
        'faults': ('unstable_sort_bug',),
    },
}


@dataclass
class FaultProfile:
    slow_ui: bool = False
    duplicate_create_bug: bool = False
    unstable_sort_bug: bool = False
    search_bug: bool = False
    dashboard_cache_bug: bool = False
    midnight_boundary: bool = False


def fault_names() -> tuple[str, ...]:
    return tuple(FAULT_LABELS.keys())


def preset_names() -> tuple[str, ...]:
    return tuple(PRESET_DEFINITIONS.keys())


def _normalize_profile(raw: Mapping[str, Any] | None = None) -> FaultProfile:
    values = {name: False for name in fault_names()}
    if raw:
        for name in fault_names():
            values[name] = bool(raw.get(name, False))
    return FaultProfile(**values)


def _session_from(source: Any | None) -> MutableMapping[str, Any] | None:
    if source is None:
        return None
    session = getattr(source, 'session', None)
    if session is not None:
        return session
    if hasattr(source, 'get'):
        return source
    return None


def get_fault_profile(source: Any | None = None) -> FaultProfile:
    session = _session_from(source)
    raw = session.get(PROFILE_SESSION_KEY, {}) if session is not None else {}
    return _normalize_profile(raw)


def profile_dict(source: Any | FaultProfile | None = None) -> dict[str, bool]:
    if isinstance(source, FaultProfile):
        return asdict(source)
    return asdict(get_fault_profile(source))


def active_fault_names(source: Any | FaultProfile | None = None) -> list[str]:
    profile = source if isinstance(source, FaultProfile) else get_fault_profile(source)
    return [name for name, enabled in profile_dict(profile).items() if enabled]


def set_fault_profile(session: MutableMapping[str, Any], **kwargs: Any) -> FaultProfile:
    current = profile_dict(session)
    for key, value in kwargs.items():
        if key in current:
            current[key] = bool(value)
    session[PROFILE_SESSION_KEY] = current
    clear_cached_dashboard(session)
    return _normalize_profile(current)


def toggle_fault(session: MutableMapping[str, Any], fault_name: str) -> FaultProfile:
    current = profile_dict(session)
    if fault_name not in current:
        raise KeyError(fault_name)
    current[fault_name] = not current[fault_name]
    session[PROFILE_SESSION_KEY] = current
    clear_cached_dashboard(session)
    return _normalize_profile(current)


def reset_fault_profile(session: MutableMapping[str, Any] | None = None) -> FaultProfile:
    if session is None:
        return FaultProfile()
    session.pop(PROFILE_SESSION_KEY, None)
    clear_cached_dashboard(session)
    return FaultProfile()


def apply_fault_preset(session: MutableMapping[str, Any], preset_name: str) -> FaultProfile:
    preset = PRESET_DEFINITIONS.get(preset_name)
    if preset is None:
        raise KeyError(preset_name)
    values = {name: False for name in fault_names()}
    for fault_name in preset['faults']:
        values[fault_name] = True
    session[PROFILE_SESSION_KEY] = values
    clear_cached_dashboard(session)
    return _normalize_profile(values)


def get_cached_dashboard(source: Any | None = None) -> dict[str, int] | None:
    session = _session_from(source)
    if session is None:
        return None
    cached = session.get(DASHBOARD_CACHE_KEY)
    return cached if isinstance(cached, dict) else None


def set_cached_dashboard(session: MutableMapping[str, Any], value: dict[str, int]) -> None:
    session[DASHBOARD_CACHE_KEY] = value


def clear_cached_dashboard(session: MutableMapping[str, Any] | None) -> None:
    if session is None:
        return
    session.pop(DASHBOARD_CACHE_KEY, None)


def fault_cards(source: Any | FaultProfile | None = None) -> list[dict[str, Any]]:
    profile = source if isinstance(source, FaultProfile) else get_fault_profile(source)
    values = profile_dict(profile)
    return [
        {
            'name': name,
            'label': FAULT_LABELS[name],
            'description': FAULT_DESCRIPTIONS[name],
            'enabled': values[name],
        }
        for name in fault_names()
    ]


def preset_cards() -> list[dict[str, Any]]:
    return [
        {
            'name': name,
            'label': preset['label'],
            'description': preset['description'],
            'fault_labels': [FAULT_LABELS[fault_name] for fault_name in preset['faults']],
        }
        for name, preset in PRESET_DEFINITIONS.items()
    ]
