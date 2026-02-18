"""
Friday Memory Layer
Intent memory, habit learning, facts, notes, goals, reminders.
"""
import json
from db.database import (
    learn_habit, get_habit, list_habits,
    add_fact, search_facts, list_facts,
    add_note, list_notes, search_notes,
    add_reminder, get_due_reminders, get_pending_reminders, complete_reminder,
    add_goal, update_goal, list_goals,
    set_pref, get_pref,
)
from dataclasses import dataclass
from typing import Optional

@dataclass
class R:
    ok: bool; out: str


# ── Intent / habit memory ──────────────────────────────────────────────────────

def remember_preference(action: str, choice: str):
    """Record that the user chose 'choice' when doing 'action'."""
    learn_habit(action, choice)
    return R(True, f"Remembered: for '{action}' → use '{choice}'")


def recall_preference(action: str) -> Optional[str]:
    """Return stored preference for an action, or None."""
    h = get_habit(action)
    return h["preference"] if h else None


def get_habits_summary() -> str:
    habits = list_habits()
    if not habits:
        return "No habits learned yet."
    lines = [f"  {h['action']:<35} → {h['preference']}  (×{h['count']})" for h in habits[:20]]
    return "Learned habits:\n" + "\n".join(lines)


def infer_preferences(user_input: str, tool: str, args: dict) -> dict:
    """
    Augment args with learned preferences before dispatch.
    E.g. always use pip, always connect to HomeNet, etc.
    """
    enhanced = dict(args)

    # Package manager preference
    if tool == "install_package" and "manager" not in args:
        pref = recall_preference("package_manager")
        if pref:
            enhanced["manager"] = pref

    # WiFi — fill stored password
    if tool == "connect_wifi" and "password" not in args:
        from db.database import get_wifi
        stored = get_wifi(args.get("ssid",""))
        if stored and stored.get("password"):
            enhanced["password"] = stored["password"]

    # Volume — remember last level
    if tool == "set_volume" and "level" not in args:
        pref = recall_preference("volume_level")
        if pref:
            enhanced["level"] = int(pref)

    return enhanced


def record_tool_choice(tool: str, args: dict):
    """After successful tool use, learn preferences."""
    if tool == "install_package" and "manager" in args:
        learn_habit("package_manager", args["manager"])
    if tool == "set_volume" and "level" in args:
        learn_habit("volume_level", str(args["level"]))
    if tool == "connect_wifi" and "ssid" in args:
        learn_habit("last_wifi", args["ssid"])
    if tool == "connect_bluetooth" and "name_or_mac" in args:
        learn_habit("last_bt", args["name_or_mac"])
    if tool == "launch_app" and "app_name" in args:
        learn_habit(f"app_{args['app_name']}", args["app_name"])


# ── Facts ──────────────────────────────────────────────────────────────────────

def remember_fact(content, category="general", importance=1.0):
    add_fact(content, category, importance)
    return R(True, f"Remembered: {content}")

def recall_facts(query):
    facts = search_facts(query)
    if not facts:
        return R(True, f"No facts found for '{query}'")
    lines = [f"  [{f['category']}] {f['content']}" for f in facts]
    return R(True, "Facts:\n" + "\n".join(lines))

def show_facts(category=None):
    facts = list_facts(category)
    if not facts:
        return R(True, "No facts stored")
    lines = [f"  [{f['category']}] {f['content']}" for f in facts]
    return R(True, "All facts:\n" + "\n".join(lines))


# ── Notes ──────────────────────────────────────────────────────────────────────

def save_note(title, content, tags=None):
    add_note(title, content, tags or [])
    return R(True, f"Note saved: {title}")

def show_notes():
    notes = list_notes()
    if not notes:
        return R(True, "No notes saved")
    lines = [f"  [{n['id']}] {n['title']} — {n['updated_at'][:10]}" for n in notes]
    return R(True, "Notes:\n" + "\n".join(lines))

def find_note(query):
    notes = search_notes(query)
    if not notes:
        return R(True, f"No notes matching '{query}'")
    out = []
    for n in notes:
        out.append(f"── {n['title']} ──\n{n['content'][:300]}")
    return R(True, "\n\n".join(out))


# ── Reminders ──────────────────────────────────────────────────────────────────

def add_reminder_nlp(text, when_str, repeat="none", priority="normal"):
    """Parse natural language time like 'in 2 hours', 'tomorrow 9am'."""
    from datetime import datetime, timedelta
    import re
    now = datetime.now()

    when_str = when_str.lower().strip()

    # "in X minutes/hours/days"
    m = re.match(r"in (\d+) (minute|hour|day|week)s?", when_str)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"minute": timedelta(minutes=n), "hour": timedelta(hours=n),
                 "day": timedelta(days=n), "week": timedelta(weeks=n)}[unit]
        due = (now + delta).isoformat()
    elif "tomorrow" in when_str:
        due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0).isoformat()
    elif "tonight" in when_str or "evening" in when_str:
        due = now.replace(hour=21, minute=0, second=0).isoformat()
    elif "morning" in when_str:
        due = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0).isoformat()
    else:
        try:
            from dateutil import parser as dp
            due = dp.parse(when_str, default=now).isoformat()
        except Exception:
            return R(False, f"Cannot parse time: '{when_str}'. Try 'in 2 hours' or 'tomorrow 9am'")

    rid = add_reminder(text, due, repeat, priority)
    return R(True, f"⏰ Reminder set: '{text}' at {due[:16]} (id:{rid})")

def show_reminders():
    reminders = get_pending_reminders()
    if not reminders:
        return R(True, "No pending reminders")
    icons = {"high": "🔴", "normal": "🟡", "low": "🟢"}
    lines = [f"  {icons.get(r['priority'],'·')} [{r['id']}] {r['text']:<40} due:{r['due_time'][:16]}" for r in reminders]
    return R(True, "Reminders:\n" + "\n".join(lines))

def done_reminder(rid):
    complete_reminder(rid)
    return R(True, f"Reminder #{rid} marked done")


# ── Goals ──────────────────────────────────────────────────────────────────────

def create_goal(title, description="", steps=None):
    gid = add_goal(title, description, steps)
    return R(True, f"Goal created: {title} (id:{gid})")

def progress_goal(gid, progress):
    update_goal(gid, progress=progress)
    return R(True, f"Goal #{gid} → {progress}%")

def complete_goal(gid):
    update_goal(gid, status="completed")
    return R(True, f"Goal #{gid} completed 🎉")

def show_goals(status="active"):
    goals = list_goals(status)
    if not goals:
        return R(True, f"No {status} goals")
    bar = lambda p: "█"*int(p/10)+"░"*(10-int(p/10))
    lines = [f"  [{g['id']}] {g['title']:<35} [{bar(g['progress'])}] {g['progress']}%" for g in goals]
    return R(True, f"{status.title()} goals:\n" + "\n".join(lines))


# ── Context builder (used by agent) ───────────────────────────────────────────

def build_context() -> str:
    """Build a rich context string injected into every system prompt."""
    parts = []

    # Due reminders
    due = get_due_reminders()
    if due:
        parts.append(f"DUE REMINDERS ({len(due)}): " + " | ".join(r["text"] for r in due[:3]))

    # Active goals
    goals = list_goals("active")
    if goals:
        parts.append(f"ACTIVE GOALS ({len(goals)}): " + " | ".join(f"{g['title']} {g['progress']}%" for g in goals[:3]))

    # Habits
    habits = list_habits()
    if habits:
        prefs = [f"{h['action']}={h['preference']}" for h in habits[:5]]
        parts.append("PREFERENCES: " + ", ".join(prefs))

    return "\n".join(parts) if parts else ""
