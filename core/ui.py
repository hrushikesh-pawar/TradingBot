import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def silence_third_party_noise():
    """Silences noisy tracebacks and deep debug output from APIs and libraries."""
    for name in ["urllib3", "yfinance", "peewee", "google", "requests"]:
        logging.getLogger(name).setLevel(logging.CRITICAL)

def display_banner(market_title: str, capital: float, risk_pct: float):
    risk_rupees = capital * risk_pct
    summary = f"[bold white]Capital:[/bold white] [green]₹{capital:,.2f}[/green]  |  [bold white]Risk/Trade:[/bold white] [yellow]{risk_pct*100:.1f}% (₹{risk_rupees:,.2f})[/yellow]"
    console.print(Panel(summary, title=f"[bold cyan]{market_title}[/bold cyan]", expand=False))

def print_status(symbol: str, message: str, status_type: str = "info"):
    colors = {
        "info": "dim cyan",
        "wait": "yellow",
        "skip": "dim",
        "success": "bold green",
        "error": "bold red"
    }
    color = colors.get(status_type, "white")
    console.print(f"  [{color}]•[/{color}] [bold]{symbol:<14}[/bold] : [{color}]{message}[/{color}]")

def render_summary_table(title: str, records: list):
    """Prints a structured summary table of the scan."""
    table = Table(title=f"\n[bold]{title}[/bold]", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="bold white", width=14)
    table.add_column("Price", justify="right", width=12)
    table.add_column("Action", justify="center", width=8)
    table.add_column("Shares/Units", justify="right", width=14)
    table.add_column("Max Risk", justify="right", width=12)
    table.add_column("Status / Edge", justify="left")

    for r in records:
        table.add_row(
            r["symbol"],
            r["price"],
            r["action"],
            str(r["units"]),
            r["risk"],
            r["status"]
        )
    console.print(table)