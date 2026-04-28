"""SQLite ledger.

Money is stored as INTEGER cents to avoid float drift over many additions.
The Python API still accepts and returns USD floats — conversion happens
at the boundary via cents() / usd().
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from chase_agent import config

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    target TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    anomalies TEXT,
    snapshot_path TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    posted_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    merchant TEXT NOT NULL,
    raw_description TEXT,
    category TEXT,
    card TEXT NOT NULL DEFAULT 'CSR',
    is_credit_offset INTEGER NOT NULL DEFAULT 0,
    triggered_perk_id TEXT,
    scrape_run_id INTEGER REFERENCES scrape_runs(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_posted ON transactions(posted_date);
CREATE INDEX IF NOT EXISTS idx_tx_perk ON transactions(triggered_perk_id);

CREATE TABLE IF NOT EXISTS credits_state (
    perk_id TEXT NOT NULL,
    period_key TEXT NOT NULL,
    used_cents INTEGER NOT NULL DEFAULT 0,
    total_cents INTEGER NOT NULL,
    expires_iso TEXT,
    last_scraped_at TEXT NOT NULL,
    PRIMARY KEY (perk_id, period_key)
);

CREATE TABLE IF NOT EXISTS activations (
    perk_id TEXT PRIMARY KEY,
    active INTEGER NOT NULL DEFAULT 0,
    activated_at TEXT,
    last_verified_at TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS behavior_overrides (
    perk_id TEXT PRIMARY KEY,
    reason TEXT,
    suppress_until TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    perk_id TEXT NOT NULL,
    action TEXT NOT NULL,
    estimated_value_cents INTEGER,
    deadline TEXT,
    score REAL NOT NULL,
    surfaced_at TEXT NOT NULL,
    outcome TEXT,
    outcome_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_rec_perk ON recommendations_history(perk_id);
CREATE INDEX IF NOT EXISTS idx_rec_surfaced ON recommendations_history(surfaced_at);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    markdown_path TEXT,
    summary_json TEXT
);
"""


def cents(usd: float) -> int:
    """Convert USD float to cents int (banker's rounding)."""
    return round(usd * 100)


def usd(cents_value: int) -> float:
    """Convert cents int to USD float."""
    return cents_value / 100.0


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    config.ensure_dirs()
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(?, ?)",
            (SCHEMA_VERSION, now_iso()),
        )


def now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


# ---------- config ----------
def get_config(key: str) -> str | None:
    with conn() as c:
        row = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_config(key: str, value: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO config(key,value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, now_iso()),
        )


def load_user_config() -> config.UserConfig:
    raw = get_config("user_config")
    if raw is None:
        return config.UserConfig()
    return config.UserConfig.model_validate_json(raw)


def save_user_config(cfg: config.UserConfig) -> None:
    set_config("user_config", cfg.model_dump_json())


# ---------- credits ----------
def upsert_credit_state(
    perk_id: str,
    period_key: str,
    used_usd: float,
    total_usd: float,
    expires_iso: str | None,
) -> None:
    with conn() as c:
        c.execute(
            """
            INSERT INTO credits_state(
                perk_id, period_key, used_cents, total_cents, expires_iso, last_scraped_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(perk_id,period_key) DO UPDATE SET
                used_cents=excluded.used_cents,
                total_cents=excluded.total_cents,
                expires_iso=excluded.expires_iso,
                last_scraped_at=excluded.last_scraped_at
            """,
            (perk_id, period_key, cents(used_usd), cents(total_usd), expires_iso, now_iso()),
        )


def _row_to_credit_state(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """DB row -> API shape: cents -> USD floats kept alongside cents."""
    d = dict(row)
    if "used_cents" in d:
        d["used_usd"] = usd(int(d["used_cents"]))
    if "total_cents" in d:
        d["total_usd"] = usd(int(d["total_cents"]))
    return d


def get_credit_state(perk_id: str, period_key: str) -> dict[str, Any] | None:
    with conn() as c:
        row = c.execute(
            "SELECT * FROM credits_state WHERE perk_id=? AND period_key=?",
            (perk_id, period_key),
        ).fetchone()
        return _row_to_credit_state(row) if row else None


def all_credit_states() -> list[dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT * FROM credits_state ORDER BY perk_id, period_key").fetchall()
        return [_row_to_credit_state(r) for r in rows]


# ---------- activations ----------
def set_activation(perk_id: str, active: bool, notes: str | None = None) -> None:
    with conn() as c:
        c.execute(
            """
            INSERT INTO activations(perk_id,active,activated_at,last_verified_at,notes)
            VALUES(?,?,?,?,?)
            ON CONFLICT(perk_id) DO UPDATE SET
                active=excluded.active,
                activated_at=COALESCE(activations.activated_at, excluded.activated_at),
                last_verified_at=excluded.last_verified_at,
                notes=excluded.notes
            """,
            (perk_id, 1 if active else 0, now_iso() if active else None, now_iso(), notes),
        )


def all_activations() -> dict[str, dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT * FROM activations").fetchall()
        return {r["perk_id"]: dict(r) for r in rows}


# ---------- overrides ----------
def add_override(perk_id: str, reason: str | None, suppress_until: date | None = None) -> None:
    with conn() as c:
        c.execute(
            """
            INSERT INTO behavior_overrides(perk_id,reason,suppress_until,created_at)
            VALUES(?,?,?,?)
            ON CONFLICT(perk_id) DO UPDATE SET
                reason=excluded.reason,
                suppress_until=excluded.suppress_until
            """,
            (perk_id, reason, suppress_until.isoformat() if suppress_until else None, now_iso()),
        )


def remove_override(perk_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM behavior_overrides WHERE perk_id=?", (perk_id,))


def all_overrides() -> dict[str, dict[str, Any]]:
    with conn() as c:
        rows = c.execute("SELECT * FROM behavior_overrides").fetchall()
        return {r["perk_id"]: dict(r) for r in rows}


# ---------- transactions ----------
def insert_transaction(
    *,
    id: str,
    posted_date: date,
    amount_usd: float,
    merchant: str,
    raw_description: str | None,
    category: str | None,
    card: str = "CSR",
    is_credit_offset: bool = False,
    triggered_perk_id: str | None = None,
    scrape_run_id: int | None = None,
) -> None:
    """Upsert (not INSERT OR IGNORE): Chase sometimes reposts a tx with corrections."""
    ts = now_iso()
    with conn() as c:
        c.execute(
            """
            INSERT INTO transactions(
                id,posted_date,amount_cents,merchant,raw_description,category,
                card,is_credit_offset,triggered_perk_id,scrape_run_id,
                created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                posted_date=excluded.posted_date,
                amount_cents=excluded.amount_cents,
                merchant=excluded.merchant,
                raw_description=excluded.raw_description,
                category=excluded.category,
                card=excluded.card,
                is_credit_offset=excluded.is_credit_offset,
                triggered_perk_id=excluded.triggered_perk_id,
                scrape_run_id=excluded.scrape_run_id,
                updated_at=excluded.updated_at
            """,
            (
                id,
                posted_date.isoformat(),
                cents(amount_usd),
                merchant,
                raw_description,
                category,
                card,
                1 if is_credit_offset else 0,
                triggered_perk_id,
                scrape_run_id,
                ts,
                ts,
            ),
        )


def _row_to_tx(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    if "amount_cents" in d:
        d["amount_usd"] = usd(int(d["amount_cents"]))
    return d


def transactions_since(since: date) -> list[dict[str, Any]]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM transactions WHERE posted_date >= ? ORDER BY posted_date DESC",
            (since.isoformat(),),
        ).fetchall()
        return [_row_to_tx(r) for r in rows]


# ---------- recs ----------
def record_recommendation(
    perk_id: str,
    action: str,
    estimated_value_usd: float | None,
    deadline: date | None,
    score: float,
) -> int:
    with conn() as c:
        cur = c.execute(
            """
            INSERT INTO recommendations_history(
                perk_id,action,estimated_value_cents,deadline,score,surfaced_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                perk_id,
                action,
                cents(estimated_value_usd) if estimated_value_usd is not None else None,
                deadline.isoformat() if deadline else None,
                score,
                now_iso(),
            ),
        )
        return int(cur.lastrowid or 0)


def update_recommendation_outcome(rec_id: int, outcome: str) -> None:
    with conn() as c:
        c.execute(
            "UPDATE recommendations_history SET outcome=?, outcome_at=? WHERE id=?",
            (outcome, now_iso(), rec_id),
        )


# ---------- scrape runs ----------
def start_scrape_run(target: str) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO scrape_runs(started_at,target,success) VALUES(?,?,0)",
            (now_iso(), target),
        )
        return int(cur.lastrowid or 0)


def finish_scrape_run(
    run_id: int,
    success: bool,
    anomalies: list[str] | None = None,
    snapshot_path: Path | None = None,
) -> None:
    with conn() as c:
        c.execute(
            "UPDATE scrape_runs SET finished_at=?, success=?, anomalies=?, snapshot_path=? "
            "WHERE id=?",
            (
                now_iso(),
                1 if success else 0,
                json.dumps(anomalies) if anomalies else None,
                str(snapshot_path) if snapshot_path else None,
                run_id,
            ),
        )


def last_scrape_run() -> dict[str, Any] | None:
    with conn() as c:
        row = c.execute("SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None


# ---------- reset / wipe ----------
def wipe_all() -> None:
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    init_db()
