"""chase-agent CLI: power-user actions, config, suppression, modes."""

from __future__ import annotations

from datetime import date

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from chase_agent import config, db
from chase_agent.dashboard.state import build_view
from chase_agent.rules.engine import select_top_three
from chase_agent.rules.perks import ALL_PERKS, PERKS_BY_ID
from chase_agent.scraper import chase as chase_scraper

app = typer.Typer(
    no_args_is_help=True,
    help="Chase Sapphire Reserve perks optimizer.",
    rich_markup_mode="rich",
)
console = Console()


# ---------- lifecycle ----------
@app.command()
def init() -> None:
    """First-run onboarding: collect config, init DB."""
    db.init_db()
    cfg = db.load_user_config()
    console.print("[bold]chase-agent init[/bold]")

    open_raw = typer.prompt(
        "Card open date (YYYY-MM-DD), blank to skip",
        default=cfg.card_open_date.isoformat() if cfg.card_open_date else "",
        show_default=bool(cfg.card_open_date),
    )
    cfg.card_open_date = date.fromisoformat(open_raw) if open_raw else None

    sub_raw = typer.prompt(
        "Sign-up bonus start date (YYYY-MM-DD), blank if not active",
        default=cfg.sub_start_date.isoformat() if cfg.sub_start_date else "",
        show_default=bool(cfg.sub_start_date),
    )
    cfg.sub_start_date = date.fromisoformat(sub_raw) if sub_raw else None
    if cfg.sub_start_date is not None:
        cfg.sub_spend_to_date = float(
            typer.prompt("SUB spend so far (USD)", default=str(cfg.sub_spend_to_date))
        )

    cfg.phone_bill_on_csr = typer.confirm(
        "Phone bill currently paid on CSR?", default=cfg.phone_bill_on_csr
    )
    cfg.family_sharing_setup = typer.confirm(
        "Apple Family Sharing set up?", default=cfg.family_sharing_setup
    )
    cfg.cpc_active = typer.confirm("Chase Private Client active?", default=cfg.cpc_active)
    cfg.cash_buffer_threshold = float(
        typer.prompt("Cash buffer threshold (USD)", default=str(cfg.cash_buffer_threshold))
    )
    cfg.checking_balance_estimate = float(
        typer.prompt(
            "Checking balance estimate (USD, used for idle-cash trigger)",
            default=str(cfg.checking_balance_estimate),
        )
    )
    airports_raw = typer.prompt(
        "Default airports (comma-separated)", default=",".join(cfg.default_airports)
    )
    cfg.default_airports = [a.strip() for a in airports_raw.split(",") if a.strip()]
    cfg.current_5_24_count = int(
        typer.prompt("Current 5/24 count", default=str(cfg.current_5_24_count))
    )
    cfg.reactive_enabled = typer.confirm(
        "Enable reactive transaction nudges?", default=cfg.reactive_enabled
    )

    db.save_user_config(cfg)
    console.print(f"[green]Config saved at[/green] {config.DB_PATH}")


@app.command()
def status() -> None:
    """Show current state, last scrape, top actions."""
    db.init_db()
    view = build_view()
    console.print(
        f"[bold]CSR captured:[/bold] ${view.captured_usd:.0f} / ${view.annual_fee:.0f} "
        f"({view.captured_pct:.0f}%)"
    )
    if view.last_scrape_iso:
        console.print(f"Last scrape: {view.last_scrape_iso}")
    else:
        console.print("[yellow]No scrape yet.[/yellow]")

    if view.top_actions:
        console.print("\n[bold]Top actions:[/bold]")
        for i, r in enumerate(view.top_actions, start=1):
            console.print(
                f"  {i}. {r.action} "
                f"[green]${r.estimated_value_usd:.0f}[/green] "
                f"({r.effort}, conf {r.confidence:.1f})"
            )
    else:
        console.print("[green]All caught up.[/green]")


@app.command()
def scrape(
    target: str = typer.Argument("benefits", help="benefits | activity | offers"),
    skip_verify: bool = typer.Option(False, "--skip-verify", help="Skip LLM dual-pass"),
) -> None:
    """Run a chrome-agent scrape against Chase. Requires ANTHROPIC_API_KEY + chrome-agent."""
    db.init_db()
    if target != "benefits":
        console.print(f"[yellow]Target '{target}' not implemented yet.[/yellow]")
        raise typer.Exit(code=1)

    console.print("[bold]Scraping Chase Card Benefits...[/bold]")
    try:
        result = chase_scraper.scrape_card_benefits(skip_verify=skip_verify)
    except Exception as e:
        console.print(f"[red]Scrape failed:[/red] {type(e).__name__}: {e}")
        raise typer.Exit(code=1) from e

    if not result["success"]:
        console.print(f"[red]Scrape unsuccessful.[/red] anomalies={result['anomalies']}")
        raise typer.Exit(code=1)

    console.print(
        f"[green]Scraped[/green] {len(result.get('credits', []))} credits, "
        f"{len(result.get('activations', []))} activations."
    )
    if result.get("anomalies"):
        console.print(f"[yellow]Anomalies:[/yellow] {result['anomalies']}")


REPORT_TITLES: dict[str, str] = {
    "weekly": "Weekly Card Maximizer",
    "monthly": "Monthly Sweep — Lyft / DoorDash / Peloton / Instacart",
    "half-year": "Half-Year Sweep — Dining + StubHub",
}


@app.command()
def report(kind: str = typer.Argument("weekly", help="weekly | monthly | half-year")) -> None:
    """Generate a report markdown file."""
    db.init_db()
    if kind not in REPORT_TITLES:
        console.print(f"[red]Unknown report kind:[/red] {kind}")
        console.print(f"Known: {', '.join(REPORT_TITLES)}")
        raise typer.Exit(code=1)
    view = build_view()
    out = config.REPORT_DIR / f"{kind}-{view.today.isoformat()}.md"
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    title = REPORT_TITLES[kind]
    lines: list[str] = [
        f"# {title} ({view.today.isoformat()})",
        "",
        f"Captured ${view.captured_usd:.0f} / ${view.annual_fee:.0f} ({view.captured_pct:.0f}%).",
        "",
    ]
    if view.top_actions:
        lines.append("## Top actions")
        for i, r in enumerate(view.top_actions, start=1):
            lines.extend(
                [
                    f"### {i}. {r.action}",
                    f"- Value: ~${r.estimated_value_usd:.0f}",
                    f"- Effort: {r.effort}",
                    f"- Confidence: {r.confidence:.1f}",
                    f"- Reason: {r.reason}",
                    f"- Next: {r.next_step}",
                    "",
                ]
            )
    out.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[green]Report written:[/green] {out}")


# ---------- suppress ----------
@app.command()
def suppress(
    perk_id: str,
    reason: str = typer.Option("", "--reason", help="Why you're suppressing this"),
) -> None:
    """Stop suggesting a perk."""
    db.init_db()
    if perk_id not in PERKS_BY_ID:
        console.print(f"[red]Unknown perk:[/red] {perk_id}")
        console.print("Known perks: " + ", ".join(p.id for p in ALL_PERKS))
        raise typer.Exit(code=1)
    db.add_override(perk_id, reason or None)
    console.print(f"[green]Suppressed[/green] {perk_id}")


@app.command()
def unsuppress(perk_id: str) -> None:
    """Resume suggestions for a perk."""
    db.init_db()
    db.remove_override(perk_id)
    console.print(f"[green]Unsuppressed[/green] {perk_id}")


@app.command()
def overrides() -> None:
    """List active suppressions."""
    db.init_db()
    items = db.all_overrides()
    if not items:
        console.print("No overrides active.")
        return
    t = Table(title="Active suppressions")
    t.add_column("perk_id")
    t.add_column("reason")
    t.add_column("suppress_until")
    for k, v in items.items():
        t.add_row(k, v.get("reason") or "-", v.get("suppress_until") or "-")
    console.print(t)


# ---------- reactive ----------
@app.command()
def reactive(state: str = typer.Argument(..., help="on | off | status")) -> None:
    """Toggle reactive transaction nudges."""
    db.init_db()
    cfg = db.load_user_config()
    if state == "on":
        cfg.reactive_enabled = True
        db.save_user_config(cfg)
        console.print("[green]Reactive mode ON[/green]")
    elif state == "off":
        cfg.reactive_enabled = False
        db.save_user_config(cfg)
        console.print("[yellow]Reactive mode OFF[/yellow]")
    elif state == "status":
        console.print(f"reactive_enabled={cfg.reactive_enabled}")
        console.print(f"floor=${cfg.reactive_floor_usd:.0f}")
        console.print(f"quiet_hours={cfg.reactive_quiet_start:02d}-{cfg.reactive_quiet_end:02d}")
    else:
        console.print(f"[red]Unknown state: {state}[/red]")
        raise typer.Exit(code=1)


# ---------- activations ----------
@app.command()
def activations() -> None:
    """List status of all activatable perks."""
    db.init_db()
    view = build_view()
    t = Table(title="Activations")
    t.add_column("perk")
    t.add_column("status")
    t.add_column("deadline")
    t.add_column("days_left")
    for a in view.activations:
        status_text = "[green]active[/green]" if a.active else "[red]inactive[/red]"
        t.add_row(
            a.name,
            status_text,
            a.deadline_iso or "-",
            str(a.days_remaining) if a.days_remaining is not None else "-",
        )
    console.print(t)


@app.command()
def activate(perk_id: str) -> None:
    """Mark an activatable perk as activated (manual override)."""
    db.init_db()
    perk = PERKS_BY_ID.get(perk_id)
    if perk is None:
        console.print(f"[red]Unknown perk:[/red] {perk_id}")
        raise typer.Exit(code=1)
    if not perk.activation_required:
        console.print(
            f"[red]Perk '{perk_id}' is not activatable.[/red] "
            "Only perks with activation_required=True can be activated."
        )
        raise typer.Exit(code=1)
    db.set_activation(perk_id, active=True, notes="manually marked")
    console.print(f"[green]Activated[/green] {perk_id}")


# ---------- modes ----------
@app.command(name="card-for")
def card_for(query: str) -> None:
    """Recommend best card for a purchase. LLM-powered (Phase 3)."""
    console.print(f"[yellow]card-for not implemented yet (Phase 3): '{query}'[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def trip(query: str) -> None:
    """Trip optimizer. LLM-powered (Phase 3)."""
    console.print(f"[yellow]trip not implemented yet (Phase 3): '{query}'[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def redeem(query: str) -> None:
    """Redemption advisor. LLM-powered (Phase 3)."""
    console.print(f"[yellow]redeem not implemented yet (Phase 3): '{query}'[/yellow]")
    raise typer.Exit(code=1)


# ---------- maintenance ----------
@app.command()
def reauth() -> None:
    """Re-copy cookies from main Chrome (Phase 2)."""
    console.print("[yellow]reauth not implemented yet (Phase 2).[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def wipe(
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Nuke all local state."""
    if not yes and not typer.confirm("Wipe ALL local state?", default=False):
        raise typer.Abort
    db.wipe_all()
    console.print(f"[green]Wiped[/green] {config.DB_PATH}")


@app.command()
def dashboard(
    port: int = typer.Option(config.DASHBOARD_PORT, help="Port to bind"),
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
) -> None:
    """Run the local dashboard."""
    uvicorn.run("chase_agent.dashboard.app:app", host=host, port=port, log_level="info")


@app.command(name="config")
def config_cmd() -> None:
    """Show current user config."""
    db.init_db()
    cfg = db.load_user_config()
    for k, v in cfg.model_dump().items():
        console.print(f"  {k} = {v}")


@app.command(name="config-set")
def config_set(key: str, value: str) -> None:
    """Set a single user-config field. Type-coerced based on existing field type."""
    db.init_db()
    cfg = db.load_user_config()
    data = cfg.model_dump()
    if key not in data:
        console.print(f"[red]Unknown config key:[/red] {key}")
        console.print(f"Known keys: {', '.join(data)}")
        raise typer.Exit(code=1)
    current = data[key]
    coerced: object
    try:
        if isinstance(current, bool):
            coerced = value.lower() in ("1", "true", "yes", "y", "on")
        elif isinstance(current, int):
            coerced = int(value)
        elif isinstance(current, float):
            coerced = float(value)
        elif isinstance(current, list):
            coerced = [v.strip() for v in value.split(",") if v.strip()]
        else:
            coerced = value
    except (ValueError, TypeError) as e:
        console.print(f"[red]Cannot coerce[/red] '{value}' to {type(current).__name__}: {e}")
        raise typer.Exit(code=1) from e
    data[key] = coerced
    db.save_user_config(type(cfg).model_validate(data))
    console.print(f"[green]Set[/green] {key} = {coerced}")


# ---------- top-level diagnostics ----------
@app.command()
def recs() -> None:
    """Show every recommendation (top + ignored)."""
    db.init_db()
    view = build_view()
    all_recs = view.top_actions + view.ignored
    sorted_recs, _ = select_top_three(all_recs)
    for r in all_recs:
        marker = "*" if r in view.top_actions else " "
        console.print(
            f"{marker} [bold]{r.score:6.1f}[/bold]  {r.action}  "
            f"(${r.estimated_value_usd:.0f}, {r.effort})"
        )
    _ = sorted_recs


if __name__ == "__main__":
    app()
