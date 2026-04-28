"""Configuration: paths, env, user manual config."""

import os
from datetime import date
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import BaseModel, Field


def _data_dir() -> Path:
    override = os.environ.get("CHASE_AGENT_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return Path(user_data_dir("chase-agent", "sderosiaux"))


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "ledger.db"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
REPORT_DIR = DATA_DIR / "reports"
DASHBOARD_PORT = int(os.environ.get("CHASE_AGENT_DASHBOARD_PORT", "7777"))


class UserConfig(BaseModel):
    """Manual config from onboarding. Persisted in DB `config` table."""

    card_open_date: date | None = None
    sub_start_date: date | None = None
    sub_spend_to_date: float = 0.0
    sub_state: str = "inactive"  # inactive|active|on_pace|behind|cleared|archived
    cash_buffer_threshold: float = 25_000.0
    checking_balance_estimate: float = 0.0
    default_airports: list[str] = Field(default_factory=lambda: ["JFK", "LGA", "EWR"])
    home_city: str = "NYC"
    phone_bill_on_csr: bool = False
    family_sharing_setup: bool = False
    cpc_active: bool = True
    current_5_24_count: int = 0
    loyalty_ids: dict[str, str] = Field(default_factory=dict)
    pet_categories_blocked: list[str] = Field(default_factory=list)
    reactive_enabled: bool = True
    reactive_floor_usd: float = 5.0
    reactive_quiet_start: int = 22  # NYC hour
    reactive_quiet_end: int = 8


def ensure_dirs() -> None:
    for d in (DATA_DIR, SNAPSHOT_DIR, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
