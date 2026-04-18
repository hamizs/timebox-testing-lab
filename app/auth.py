from fastapi import Request
from .db import get_conn

SESSION_KEY = 'user_id'


def current_user(request: Request):
    user_id = request.session.get(SESSION_KEY)
    if not user_id:
        return None
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
