"""
Interactive CLI demo — shows the Customer Memory Card in a readable format.
Run: python demo_cli.py           (pause between scenarios)
Run: python demo_cli.py --no-pause (run all scenarios without stopping)
"""
import sys
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from datetime import datetime

BASE = "http://localhost:8000"
console = Console()


def print_memory_card(card: dict):
    customer_id = card["customer_id"]
    role = card["agent_role"]
    gov = card["governance"]
    memories = card["memories"]
    citations = card["citations"]

    # Header
    console.print()
    console.rule(f"[bold cyan]CUSTOMER MEMORY CARD[/bold cyan]")
    console.print(f"  Customer: [bold]{customer_id}[/bold]   Agent role: [yellow]{role}[/yellow]   Generated: {card['generated_at'][:19]}")
    console.print()

    # Governance summary
    g_table = Table(box=box.SIMPLE, show_header=False)
    g_table.add_column("", style="dim")
    g_table.add_column("")
    g_table.add_row("Total memories", str(gov["total_memories"]))
    g_table.add_row("Allowed to this role", f"[green]{gov['allowed_memories']}[/green]")
    g_table.add_row("Blocked by ACL", f"[red]{gov['blocked_by_acl']}[/red]" if gov["blocked_by_acl"] else "0")
    g_table.add_row("Expired (purged)", str(gov["expired_count"]))
    g_table.add_row("Stale warnings", f"[yellow]{gov['stale_count']}[/yellow]" if gov["stale_count"] else "0")
    g_table.add_row("PII masked", f"[magenta]{gov['pii_masked_count']}[/magenta]" if gov["pii_masked_count"] else "0")
    console.print(Panel(g_table, title="[bold]Governance Summary[/bold]", border_style="blue"))

    # Memory items
    for i, mem in enumerate(memories, 1):
        stale = mem.get("stale_warning")
        masked = mem.get("pii_masked", False)

        badges = []
        if stale:
            badges.append("[yellow]⚠ STALE[/yellow]")
        if masked:
            badges.append("[magenta]🔒 PII MASKED[/magenta]")

        badge_str = "  " + "  ".join(badges) if badges else ""
        title = f"[bold]{i}. {mem['source_ref']}[/bold]  [dim]{mem['source_type']}[/dim]  confidence={mem['confidence']:.0%}{badge_str}"

        content_text = Text(mem["content"])
        body = content_text
        if stale:
            body = Text.assemble(body, "\n", Text(f"⚠ {stale}", style="yellow"))

        expires = mem["expires_at"][:10]
        footer = f"[dim]ID: {mem['id'][:8]}...   Expires: {expires}   Tags: {', '.join(mem['tags']) or '—'}[/dim]"

        console.print(Panel(
            Text.assemble(body, "\n", Text.from_markup(footer)),
            title=title,
            border_style="yellow" if stale else "green",
            padding=(0, 1),
        ))

    # Citations
    if citations:
        console.print(f"\n[bold]Sources cited:[/bold] " + " · ".join(f"[cyan]{c}[/cyan]" for c in citations))
    console.print()


def run_demo(pause: bool = True):
    console.print("[bold magenta]Metaworkers.AI — Governed Memory Demo[/bold magenta]")
    console.print("Connecting to API at", BASE)

    try:
        health = httpx.get(f"{BASE}/health", timeout=3).json()
        console.print(f"[green]✓ API healthy[/green] — {health['total_memories']} memories, {health['total_customers']} customers\n")
    except Exception as e:
        console.print(f"[red]✗ Cannot reach API at {BASE}[/red]\nStart it first: uvicorn main:app --reload\n")
        return

    scenarios = [
        ("Support agent — Jane Doe, billing query", "cust_jane_001", "support", "refund billing"),
        ("Billing agent — Jane Doe, full context", "cust_jane_001", "billing", ""),
        ("Support agent — Bob Smith (PII masking demo)", "cust_bob_002", "support", "plan upgrade"),
        ("Billing agent — Bob Smith (sees PII)", "cust_bob_002", "billing", ""),
    ]

    for label, cid, role, query in scenarios:
        console.rule(f"[bold]{label}[/bold]")
        params = {"agent_role": role, "query": query, "max_results": 6}
        try:
            r = httpx.get(f"{BASE}/memory-card/{cid}", params=params, timeout=5)
            if r.status_code == 404:
                console.print(f"[yellow]No memories for {cid} — run seed_data.py first[/yellow]\n")
                continue
            r.raise_for_status()
            print_memory_card(r.json())
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Error {e.response.status_code}: {e.response.text}[/red]")
        if pause:
            input("Press Enter for next scenario...")


if __name__ == "__main__":
    no_pause = "--no-pause" in sys.argv
    run_demo(pause=not no_pause)
