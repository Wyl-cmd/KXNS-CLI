"""CLI: kxns doctor — environment diagnostic + deterministic auto-fix."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(no_args_is_help=True)
doctor_cli = app  # export alias for cli/__init__.py


@app.callback(invoke_without_command=True)
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Auto-install missing Kali tools via apt (hardcoded whitelist only). "
        "Blocklisted tools (hydra/msfconsole/etc.) are never auto-installed.",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Extended connectivity probe (similar to Web environment check).",
    ),
) -> None:
    """Check Kali Linux environment for KXNS prerequisites.

    Without --fix: dry-run, reports what's missing.
    With --fix: auto-installs missing non-blocklisted tools AND registers
    them with KXNS adapters immediately.
    """
    if full:
        _run_full_doctor(fix)
    else:
        _run_basic_doctor(fix)


def _run_basic_doctor(fix: bool) -> None:
    from kxns_cli.infra.doctor import bootstrap_postgres_kxns, run_doctor

    result = run_doctor(warn_only=False, fix=fix)

    table = Table(title="KXNS Doctor — 工具状态")
    table.add_column("工具", style="cyan")
    table.add_column("状态")
    table.add_column("联动", style="dim")

    linked_structured = set(result.structured_linked)
    linked_catalog = set(result.catalog_linked)
    blocklisted = set(result.blocklisted_skipped)

    for name, ok in sorted(result.checks.items()):
        if ok:
            if name in linked_structured:
                badge = "[green]STRUCTURED[/green]"
            elif name in linked_catalog:
                badge = "[blue]CATALOG[/blue]"
            elif name in blocklisted:
                badge = "[yellow]BLOCKLISTED[/yellow]"
            else:
                badge = "[dim]raw[/dim]"
            table.add_row(name, "[green]已装[/green]", badge)
        else:
            table.add_row(name, "[red]缺失[/red]", "[dim]—[/dim]")

    console.print(table)

    for issue in result.issues:
        console.print(f"[red]Issue:[/red] {issue}")

    if result.setup_summary:
        console.print(f"[cyan]联动摘要:[/cyan] {result.setup_summary}")

    if result.structured_linked:
        names = ", ".join(result.structured_linked)
        n = len(result.structured_linked)
        console.print(f"[green]结构化适配器已联动 ({n}):[/green] {names}")

    if result.catalog_linked:
        names = ", ".join(result.catalog_linked)
        n = len(result.catalog_linked)
        console.print(f"[blue]目录联动 ({n}):[/blue] {names}")

    if result.blocklisted_skipped:
        names = ", ".join(result.blocklisted_skipped)
        n = len(result.blocklisted_skipped)
        console.print(f"[yellow]风控跳过 (blocklisted, {n}):[/yellow] {names}")

    for hint in result.hints:
        console.print(f"[yellow]Hint:[/yellow] {hint}")

    if fix:
        ok, msg = bootstrap_postgres_kxns()
        console.print(f"[green]{msg}[/green]" if ok else f"[red]{msg}[/red]")

    if not result.ok:
        console.print("[dim]Tip: kxns doctor --full 查看完整探测[/dim]")
        raise typer.Exit(code=1)


def _run_full_doctor(fix: bool) -> None:
    from kxns_cli.infra.doctor import bootstrap_postgres_kxns, run_doctor

    console.print("[bold]KXNS Full Doctor[/bold] — complete connectivity probe")
    result = run_doctor(warn_only=False, fix=fix)

    table = Table(title="Full Doctor")
    table.add_column("Check")
    table.add_column("Status")

    linked_structured = set(result.structured_linked)
    linked_catalog = set(result.catalog_linked)

    for name, ok in sorted(result.checks.items()):
        if ok:
            if name in linked_structured:
                status = "[green]已装 (结构化联动)[/green]"
            elif name in linked_catalog:
                status = "[green]已装 (目录联动)[/green]"
            else:
                status = "[green]ok[/green]"
        else:
            status = "[red]missing[/red]"
        table.add_row(name, status)
    console.print(table)

    if result.setup_summary:
        console.print(f"[cyan]联动摘要:[/cyan] {result.setup_summary}")

    for issue in result.issues:
        console.print(f"[red]Issue:[/red] {issue}")
    for hint in result.hints:
        console.print(f"[yellow]Hint:[/yellow] {hint}")

    if fix:
        ok, msg = bootstrap_postgres_kxns()
        console.print(f"[green]{msg}[/green]" if ok else f"[red]{msg}[/red]")

    if not result.ok:
        raise typer.Exit(code=1)
