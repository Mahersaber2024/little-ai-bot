import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "soundScope"),
    "user": os.getenv("DB_USER", "market_user"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    """Return a new PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def init_db() -> None:
    """Create required tables if they don't exist. Call once on startup."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS spotify_tokens (
                    telegram_user_id BIGINT PRIMARY KEY,
                    access_token     TEXT NOT NULL,
                    refresh_token    TEXT NOT NULL,
                    expires_at       BIGINT NOT NULL,
                    scope            TEXT,
                    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state             TEXT PRIMARY KEY,
                    telegram_user_id  BIGINT NOT NULL,
                    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_user_id BIGINT PRIMARY KEY,
                    username         TEXT,
                    first_name       TEXT,
                    last_name        TEXT,
                    first_seen       TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS banned_users (
                    telegram_user_id BIGINT PRIMARY KEY,
                    banned_by        BIGINT,
                    reason           TEXT,
                    banned_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
        conn.commit()
    finally:
        conn.close()


# Known users (for join logging / admin lookups)

def record_user_seen(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
    """Insert the user on first contact. Returns True if this was a new user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (telegram_user_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_user_id) DO UPDATE SET
                    username   = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name  = EXCLUDED.last_name
                RETURNING (xmax = 0) AS inserted;
                """,
                (user_id, username, first_name, last_name),
            )
            row = cur.fetchone()
        conn.commit()
        return bool(row[0]) if row else False
    finally:
        conn.close()


# Bans

def ban_user(user_id: int, banned_by: int = None, reason: str = None) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO banned_users (telegram_user_id, banned_by, reason)
                VALUES (%s, %s, %s)
                ON CONFLICT (telegram_user_id) DO UPDATE SET
                    banned_by = EXCLUDED.banned_by,
                    reason    = EXCLUDED.reason,
                    banned_at = now();
                """,
                (user_id, banned_by, reason),
            )
        conn.commit()
    finally:
        conn.close()


def unban_user(user_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM banned_users WHERE telegram_user_id = %s;", (user_id,)
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def is_banned(user_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM banned_users WHERE telegram_user_id = %s;", (user_id,)
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def list_banned(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT telegram_user_id, banned_by, reason, banned_at "
                "FROM banned_users ORDER BY banned_at DESC LIMIT %s;",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# Token storage

def save_token(user_id: int, token_info: dict) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spotify_tokens
                    (telegram_user_id, access_token, refresh_token, expires_at, scope, updated_at)
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (telegram_user_id) DO UPDATE SET
                    access_token  = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at    = EXCLUDED.expires_at,
                    scope         = EXCLUDED.scope,
                    updated_at    = now();
                """,
                (
                    user_id,
                    token_info["access_token"],
                    token_info["refresh_token"],
                    token_info["expires_at"],
                    token_info.get("scope"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_token(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT access_token, refresh_token, expires_at, scope "
                "FROM spotify_tokens WHERE telegram_user_id = %s;",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_admin_token(admin_ids: list[int]) -> tuple[int | None, dict | None]:
    """Return (owner_id, token_info) for whichever admin has a linked
    Spotify account. If several admins are logged in, the most recently
    updated one wins. Returns (None, None) if no admin is linked yet."""
    if not admin_ids:
        return None, None

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT telegram_user_id, access_token, refresh_token, expires_at, scope "
                "FROM spotify_tokens WHERE telegram_user_id = ANY(%s) "
                "ORDER BY updated_at DESC LIMIT 1;",
                (admin_ids,),
            )
            row = cur.fetchone()
            if not row:
                return None, None
            row = dict(row)
            owner_id = row.pop("telegram_user_id")
            return owner_id, row
    finally:
        conn.close()


def delete_token(user_id: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM spotify_tokens WHERE telegram_user_id = %s;", (user_id,)
            )
        conn.commit()
    finally:
        conn.close()


# OAuth state <-> Telegram user mapping (so the callback webserver knows
# which Telegram user a given login belongs to)

def save_oauth_state(state: str, user_id: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO oauth_states (state, telegram_user_id)
                VALUES (%s, %s)
                ON CONFLICT (state) DO UPDATE SET telegram_user_id = EXCLUDED.telegram_user_id;
                """,
                (state, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def pop_oauth_state(state: str) -> int | None:
    """Return the user for a given state and delete the record."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM oauth_states WHERE state = %s RETURNING telegram_user_id;",
                (state,),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    finally:
        conn.close()
