"""
Friday Skill Registry — with Validation Gate
Only skills that PASS validation reach Friday's tool list.
Bad skills are quarantined — they cannot corrupt Friday.
"""

import threading
import importlib.util
import logging
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("friday.skills")

_registry:     dict[str, Callable] = {}
_tool_defs:    list[dict]          = []
_loaded_files: dict[str, float]    = {}
_skill_status: dict[str, dict]     = {}

_watcher_thread: Optional[threading.Thread] = None
_watcher_stop    = threading.Event()
_reload_callback = None

SKILLS_DIR = Path(__file__).parent
_SKIP = {"registry.py", "validator.py"}


def _load_one_skill(path: Path) -> dict:
    from skills.validator import validate_module
    skill_name = path.stem
    status = {"ok": False, "name": skill_name,
              "tools": [], "handlers": {}, "report": None, "error": None}

    try:
        source = path.read_text()
    except Exception as e:
        status["error"] = f"Cannot read: {e}"
        _show_error(skill_name, status["error"])
        return status

    try:
        spec = importlib.util.spec_from_file_location(f"skill_{skill_name}", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        status["error"] = f"Import failed: {e}"
        _show_rejected(skill_name, status["error"])
        return status

    try:
        report = validate_module(skill_name, mod, source)
    except Exception as e:
        status["error"] = f"Validator crashed: {e}"
        log.error(f"[skill:{skill_name}] {status['error']}")
        return status

    status["report"] = report

    if not report.passed:
        status["error"] = "Validation failed"
        _show_report_rejected(skill_name, report)
        return status

    tools    = getattr(mod, "SKILL_TOOLS",    [])
    handlers = getattr(mod, "SKILL_HANDLERS", {})
    good     = set(report.tools_ok)
    bad      = set(report.tools_bad)

    good_tools    = [t for t in tools if t.get("function",{}).get("name","") in good]
    good_handlers = {k: v for k, v in handlers.items() if k in good}

    status["ok"]       = True
    status["tools"]    = good_tools
    status["handlers"] = good_handlers

    _show_loaded(skill_name, report, len(good_tools), bad)
    return status


def load_skills():
    global _registry, _tool_defs, _loaded_files, _skill_status
    _registry = {}; _tool_defs = []; new_loaded = {}; new_status = {}

    for path in sorted(SKILLS_DIR.glob("*.py")):
        if path.name.startswith("_") or path.name in _SKIP:
            continue
        mtime = path.stat().st_mtime
        new_loaded[path.name] = mtime

        is_new = path.name not in _loaded_files
        is_mod = not is_new and _loaded_files[path.name] != mtime

        if not is_new and not is_mod:
            prev = _skill_status.get(path.stem)
            if prev:
                new_status[path.stem] = prev
                if prev["ok"]:
                    _tool_defs.extend(prev["tools"])
                    _registry.update(prev["handlers"])
            continue

        status = _load_one_skill(path)
        new_status[path.stem] = status
        if status["ok"]:
            _tool_defs.extend(status["tools"])
            _registry.update(status["handlers"])

    _loaded_files = new_loaded
    _skill_status = new_status
    return _tool_defs, _registry


def reload_skills():
    global _loaded_files
    _loaded_files = {}
    return load_skills()


def get_tool_defs() -> list:
    return _tool_defs

def get_handler(name: str):
    return _registry.get(name)

def list_loaded_skills() -> list[str]:
    return [n for n, s in _skill_status.items() if s["ok"]]

def list_failed_skills() -> list[str]:
    return [n for n, s in _skill_status.items() if not s["ok"]]

def get_skill_status(skill_name: str) -> Optional[dict]:
    return _skill_status.get(skill_name)

def skill_report(skill_name: str) -> str:
    s = _skill_status.get(skill_name)
    if not s:
        return f"Skill '{skill_name}' not found."
    return s["report"].summary() if s.get("report") else f"Error: {s.get('error','unknown')}"

def all_skills_summary() -> str:
    if not _skill_status:
        return "No skills found in skills/ folder."
    lines = [f"Skill Status ({len(_skill_status)} total):\n"]
    for name, s in sorted(_skill_status.items()):
        r = s.get("report")
        if s["ok"]:
            n = len(s["tools"])
            w = len([i for i in (r.issues if r else []) if i.level == "WARNING"])
            lines.append(f"  OK   {name:<28} {n} tools" + (f"  ({w} warnings)" if w else ""))
        else:
            lines.append(f"  FAIL {name:<28} {s.get('error','unknown')}")
    ok = sum(1 for s in _skill_status.values() if s["ok"])
    lines.append(f"\n  {ok} loaded  /  {len(_skill_status)-ok} failed")
    return "\n".join(lines)


def _show_loaded(name, report, n_good, bad_names):
    try:
        from rich.console import Console
        c = Console()
        warns = [i for i in report.issues if i.level == "WARNING"]
        if bad_names:
            c.print(f"  [yellow]⚠[/yellow]  Skill [bold]{name}[/bold]: "
                    f"[green]{n_good} tools OK[/green]  [red]{len(bad_names)} REJECTED[/red]")
            for b in bad_names:
                errs = [i for i in report.issues if i.tool == b and i.level == "ERROR"]
                for e in errs:
                    c.print(f"       [red]✗[/red] {b}: {e.message}")
        else:
            w = f"  [yellow]({len(warns)} warnings)[/yellow]" if warns else ""
            c.print(f"  [green]✓[/green]  Skill [bold]{name}[/bold]: "
                    f"[green]{n_good} tools validated[/green]{w}")
        for w in warns:
            c.print(f"       [yellow]⚠[/yellow] {w.tool or name}: {w.message}")
    except Exception:
        log.info(f"Skill loaded: {name} ({n_good} tools)")


def _show_report_rejected(name, report):
    try:
        from rich.console import Console
        from rich.panel import Panel
        c = Console()
        errors = [i for i in report.issues if i.level == "ERROR"]
        body = "\n".join(f"[red]✗[/red] [bold]{e.code}[/bold]"
                         + (f" [{e.tool}]" if e.tool else "") + f": {e.message}"
                         for e in errors[:6])
        if len(errors) > 6:
            body += f"\n... and {len(errors)-6} more errors"
        body += "\n\n[dim]Fix and save — Friday retries automatically.[/dim]"
        c.print(Panel(body, title=f"[red]Skill REJECTED: {name}[/red]",
                      border_style="red", padding=(0,1)))
    except Exception:
        log.error(f"Skill REJECTED: {name}")


def _show_error(name, error):
    try:
        from rich.console import Console
        Console().print(f"  [red]✗[/red]  Skill [bold]{name}[/bold]: [red]{error}[/red]")
    except Exception:
        log.error(f"Skill error: {name}: {error}")

def _show_rejected(name, error):
    try:
        from rich.console import Console
        from rich.panel import Panel
        c = Console()
        c.print(Panel(
            f"[red]{error}[/red]\n\n[dim]Check the file for Python errors and save again.[/dim]",
            title=f"[red]Skill REJECTED: {name}[/red]",
            border_style="red", padding=(0,1)
        ))
    except Exception:
        log.error(f"Skill rejected: {name}: {error}")


def validate_js_skill_file(path) -> str:
    from skills.validator import validate_js_skill
    return validate_js_skill(path).summary()


def _watch_skills_folder():
    while not _watcher_stop.wait(2):
        try:
            current = {p.name: p.stat().st_mtime
                       for p in SKILLS_DIR.glob("*.py")
                       if not p.name.startswith("_") and p.name not in _SKIP}
            check   = {k: v for k, v in _loaded_files.items() if k not in _SKIP}
            if current != check:
                load_skills()
                if _reload_callback:
                    _reload_callback()
        except Exception as e:
            log.warning(f"Skill watcher error: {e}")


def start_watcher(reload_callback=None):
    global _watcher_thread, _reload_callback
    if _watcher_thread and _watcher_thread.is_alive():
        return
    _reload_callback = reload_callback
    _watcher_stop.clear()
    _watcher_thread = threading.Thread(target=_watch_skills_folder, daemon=True)
    _watcher_thread.start()


def stop_watcher():
    _watcher_stop.set()
    if _watcher_thread:
        _watcher_thread.join(timeout=3)


load_skills()
