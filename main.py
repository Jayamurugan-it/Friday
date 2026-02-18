#!/usr/bin/env python3
"""
Friday AI — Single Entry Point
Starts: REPL + Flask Bridge + Scheduler + Anomaly Watcher + Process Watcher + Telegram
"""

import os
import sys
import time
import threading
import platform
from pathlib import Path

# ── Load .env ──────────────────────────────────────────────────────────────────
_env = Path(__file__).parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

# ── Add project root to path ───────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel   import Panel
from rich.text    import Text
from rich.table   import Table
from prompt_toolkit              import PromptSession
from prompt_toolkit.history      import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles       import Style as PStyle

from db.database import init_db, db_stats, get_pref, set_pref
from core.risk   import Risk

console = Console()

# ── Prompt style ──────────────────────────────────────────────────────────────
PT_STYLE = PStyle.from_dict({
    "prompt":  "#00e5ff bold",
    "arrow":   "#7c5cfc",
})

HIST_FILE = Path.home() / ".friday" / "history.txt"
HIST_FILE.parent.mkdir(parents=True, exist_ok=True)

BANNER = """\
[bold cyan]
  ███████╗██████╗ ██╗██████╗  █████╗ ██╗   ██╗     █████╗ ██╗
  ██╔════╝██╔══██╗██║██╔══██╗██╔══██╗╚██╗ ██╔╝    ██╔══██╗██║
  █████╗  ██████╔╝██║██║  ██║███████║ ╚████╔╝     ███████║██║
  ██╔══╝  ██╔══██╗██║██║  ██║██╔══██║  ╚██╔╝      ██╔══██║██║
  ██║     ██║  ██║██║██████╔╝██║  ██║   ██║        ██║  ██║██║
  ╚═╝     ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝        ╚═╝  ╚═╝╚═╝
[/bold cyan]"""

HELP = """
[bold yellow]CMD ARM[/bold yellow] — system control
  [cyan]volume 75[/cyan]                    Set volume
  [cyan]mute / unmute[/cyan]                Toggle audio
  [cyan]connect wifi HomeNet[/cyan]         Connect WiFi (uses stored password)
  [cyan]save wifi MyNet pass123[/cyan]      Store WiFi credentials
  [cyan]connect bt AirPods[/cyan]           Connect Bluetooth
  [cyan]install numpy[/cyan]                pip install numpy
  [cyan]install apt ffmpeg[/cyan]           apt install ffmpeg
  [cyan]move ~/a.txt ~/docs/[/cyan]         Move file (undoable)
  [cyan]ps nginx[/cyan]                     Find process
  [cyan]kill port 3000[/cyan]               Kill process on port
  [cyan]service nginx restart[/cyan]        Systemctl
  [cyan]docker ps[/cyan]                    List containers
  [cyan]cron list[/cyan]                    List cron jobs
  [cyan]brightness 60[/cyan]                Screen brightness
  [cyan]lock[/cyan]                         Lock screen
  [cyan]sysinfo[/cyan]                      CPU/RAM/disk

[bold yellow]BROWSER ARM[/bold yellow] — Chrome extension
  [cyan]navigate to github.com[/cyan]       Open URL
  [cyan]click login button[/cyan]           Click element
  [cyan]fill form with test data[/cyan]     Fill all inputs
  [cyan]read this page[/cyan]               Extract page text
  [cyan]what is this page about?[/cyan]     Page Q&A
  [cyan]close youtube tabs[/cyan]           Tab management
  [cyan]record session checkout[/cyan]      Record steps
  [cyan]replay session checkout[/cyan]      Replay session
  [cyan]auto login github[/cyan]            Login with stored creds

[bold yellow]WEB TOOLS[/bold yellow]
  [cyan]search quantum computing[/cyan]     DuckDuckGo search
  [cyan]weather New York[/cyan]             5-day forecast
  [cyan]stock AAPL[/cyan]                   Stock price
  [cyan]100 USD to EUR[/cyan]               Currency convert
  [cyan]calculate sqrt(144)*pi[/cyan]       Math
  [cyan]wikipedia black holes[/cyan]        Wiki summary
  [cyan]test api POST localhost:3000/users[/cyan]  API test

[bold yellow]MEMORY & PRODUCTIVITY[/bold yellow]
  [cyan]remember my email is test@example.com[/cyan]
  [cyan]remind me to call mom in 2 hours[/cyan]
  [cyan]create goal: finish project[/cyan]
  [cyan]pomodoro start coding[/cyan]        25min focus timer
  [cyan]alias deploy "git add . && git push"[/cyan]
  [cyan]save snippet myloop [code][/cyan]   Code snippet
  [cyan]vault save github user pass[/cyan]  Password manager

[bold yellow]META[/bold yellow]
  [cyan]history[/cyan]  [cyan]db[/cyan]  [cyan]undo[/cyan]  [cyan]habits[/cyan]  [cyan]help[/cyan]  [cyan]exit[/cyan]

[dim]Ctrl+Enter also submits · ↑↓ history · Server: http://localhost:7723[/dim]
"""


def confirm_callback(msg: str, risk) -> bool:
    color = "red" if risk == Risk.DANGEROUS else "yellow"
    console.print()
    console.print(Panel(
        f"[{color}]{msg}[/{color}]",
        title=f"[bold {color}]{'⚠ DANGEROUS — IRREVERSIBLE' if risk == Risk.DANGEROUS else '↩ RECOVERABLE'}[/bold {color}]",
        border_style=color, padding=(0, 1),
    ))
    while True:
        try:
            ans = console.input(f"  [bold {color}]Proceed? (y/n): [/bold {color}]").strip().lower()
            if ans in ("y", "yes"): return True
            if ans in ("n", "no", ""): return False
        except (KeyboardInterrupt, EOFError):
            return False


def output_callback(text: str, style: str = ""):
    pass  # tool calls shown inline by agent


def render_banner():
    console.print(BANNER)
    console.print(Panel.fit(
        "[bold white]System + Browser AI Agent[/bold white]  ·  "
        "[green]Llama 4 Scout[/green] via [magenta]Groq[/magenta]  ·  "
        "[dim]say 'help' for all commands[/dim]",
        border_style="cyan",
    ))
    console.print()


def start_all_services(agent):
    """Launch Flask server, scheduler, watchers, Telegram in background threads."""
    from web.server import start_server_thread
    flask_host = os.getenv("FLASK_HOST", "127.0.0.1")
    flask_port = int(os.getenv("FLASK_PORT", 7723))
    start_server_thread(flask_host, flask_port)
    console.print(f"  [green]⚙[/green]  Flask bridge → [cyan]http://{flask_host}:{flask_port}[/cyan]")

    dash_port = int(os.getenv("DASHBOARD_PORT", 7724))
    # Dashboard runs on same Flask app, just different port would need another thread.
    # For simplicity, dashboard is served from the same port at /dashboard
    console.print(f"  [green]⊞[/green]  Dashboard    → [cyan]http://{flask_host}:{flask_port}/dashboard[/cyan]")

    # Scheduler
    def _proactive_msg(msg):
        console.print(f"\n  [bold cyan]Friday[/bold cyan] [dim](proactive)[/dim] {msg}\n")
    try:
        from core.scheduler import FridayScheduler
        sched = FridayScheduler(agent_callback=_proactive_msg)
        sched.start()
        console.print(f"  [green]⏰[/green]  Scheduler    → morning briefing + reminders active")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow]  Scheduler failed: {e}")

    # Anomaly watcher
    try:
        from tools.notifier import AnomalyWatcher, ProcessWatcher
        cpu_t  = int(os.getenv("CPU_ALERT_THRESHOLD",  90))
        ram_t  = int(os.getenv("RAM_ALERT_THRESHOLD",  90))
        disk_t = int(os.getenv("DISK_ALERT_THRESHOLD", 90))
        interval = int(os.getenv("PROCESS_WATCH_INTERVAL", 30))
        aw = AnomalyWatcher(cpu_t, ram_t, disk_t, interval)
        aw.start()
        pw = ProcessWatcher(interval)
        pw.start()
        console.print(f"  [green]📊[/green]  Anomaly watcher → CPU>{cpu_t}% RAM>{ram_t}% Disk>{disk_t}%")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow]  Watcher: {e}")

    # Telegram (optional)
    try:
        if os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
            from messaging.telegram import TelegramBot
            bot = TelegramBot(agent_chat_fn=agent.chat)
            bot.start()
            console.print(f"  [green]✈[/green]  Telegram bot → active")
        else:
            console.print(f"  [dim]✈  Telegram → not configured (optional)[/dim]")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow]  Telegram: {e}")

    # Skill file watcher
    try:
        from skills.registry import start_watcher
        
        def _on_skills_reload():
            count = agent.reload_skills()
            console.print(f"\n  [bold cyan]Friday[/bold cyan] [green]Skills reloaded[/green] — {count} tools available\n")
        
        start_watcher(reload_callback=_on_skills_reload)
        console.print(f"  [green]📦[/green]  Skill watcher → auto-reload on file changes")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow]  Skill watcher: {e}")


def main():
    # ── Init DB ────────────────────────────────────────────────────────────────
    init_db()
    render_banner()

    # ── API key check ──────────────────────────────────────────────────────────
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        console.print(Panel(
            "[red]GROQ_API_KEY not set.[/red]\n\n"
            "1. Copy [cyan].env.example[/cyan] → [cyan].env[/cyan]\n"
            "2. Get key from [link]https://console.groq.com[/link]\n"
            "3. Run again: [cyan]python main.py[/cyan]",
            title="[red]⚠ Setup Required[/red]", border_style="red",
        ))
        sys.exit(1)

    # ── Boot agent ─────────────────────────────────────────────────────────────
    with console.status("[bold cyan]  Booting Friday AI...[/bold cyan]", spinner="bouncingBall"):
        try:
            from core.agent import FridayAgent
            # Load skills before agent so they're available
            from skills.registry import load_skills
            skill_tools, skill_handlers = load_skills()

            agent = FridayAgent(
                confirm_callback=confirm_callback,
                output_callback=output_callback,
                extra_tools=skill_tools,
                extra_handlers=skill_handlers,
            )
            # Wire agent into Flask server for popup chat endpoint
            from web.server import set_agent
            set_agent(agent)
        except Exception as e:
            console.print(f"[red]Boot failed:[/red] {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)

    # ── Start services ─────────────────────────────────────────────────────────
    console.print(f"\n  [bold]Services:[/bold]")
    start_all_services(agent)

    # ── Show stats ─────────────────────────────────────────────────────────────
    try:
        stats = db_stats()
        console.print(
            f"\n  [green]✓[/green] [bold]Friday AI online[/bold]  ·  "
            f"[dim]{stats['commands']} commands  ·  "
            f"{stats['habits_learned']} habits  ·  "
            f"{stats['wifi_saved']} WiFi  ·  "
            f"{stats['bt_devices']} BT[/dim]\n"
        )
    except Exception:
        console.print("\n  [green]✓[/green] [bold]Friday AI online[/bold]\n")

    # ── Prompt session ─────────────────────────────────────────────────────────
    session = PromptSession(
        history=FileHistory(str(HIST_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        style=PT_STYLE,
        mouse_support=False,
    )

    # ── REPL ───────────────────────────────────────────────────────────────────
    while True:
        try:
            user_input = session.prompt([
                ("class:prompt", "  ⚡ Friday"),
                ("class:arrow",  " ❯ "),
            ]).strip()
        except KeyboardInterrupt:
            console.print("\n  [dim](Ctrl+C — type 'exit' to quit)[/dim]")
            continue
        except EOFError:
            break

        if not user_input:
            continue

        cmd = user_input.lower().strip()

        # ── Built-ins ──────────────────────────────────────────────────────────
        if cmd in ("exit", "quit", "q", "bye"):
            console.print("\n  [bold cyan]Friday:[/bold cyan] [dim]Goodbye.[/dim]\n")
            break

        if cmd in ("help", "?"):
            console.print(HELP)
            continue

        if cmd in ("clear", "cls"):
            console.clear()
            render_banner()
            continue

        # ── AI dispatch ────────────────────────────────────────────────────────
        console.print()
        t0 = time.time()

        with console.status(
            "[bold cyan]  ⚡ Friday[/bold cyan] [dim cyan]thinking...[/dim cyan]",
            spinner="bouncingBall", spinner_style="cyan",
        ):
            try:
                response = agent.chat(user_input)
            except Exception as e:
                response = f"[red]Error:[/red] {e}"
                import traceback
                console.print(traceback.format_exc(), style="dim red")

        elapsed = (time.time() - t0) * 1000

        # ── Render response ────────────────────────────────────────────────────
        if response and response.strip():
            if len(response) < 100 and "\n" not in response:
                console.print(f"  [bold cyan]Friday[/bold cyan]  {response}")
            else:
                console.print(Panel(
                    response,
                    title="[bold cyan]Friday[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                ))

        # Speed indicator
        speed_color = "green" if elapsed < 2000 else "yellow" if elapsed < 5000 else "red"
        console.print(f"\n  [dim {speed_color}]{elapsed:.0f}ms[/dim {speed_color}]\n")


if __name__ == "__main__":
    main()
