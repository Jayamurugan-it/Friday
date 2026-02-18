"""
Friday AI - Unified Database Layer
SQLite with WAL mode for fast writes.
All persistent state lives here.
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager

DB_PATH = Path.home() / ".friday" / "friday.db"


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA cache_size=-32000")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript("""
        -- Command history + undo log
        CREATE TABLE IF NOT EXISTS history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT DEFAULT (datetime('now')),
            user_input  TEXT NOT NULL,
            tool        TEXT,
            cmd         TEXT,
            risk        TEXT DEFAULT 'SAFE',
            success     INTEGER DEFAULT 1,
            output      TEXT,
            undo_cmd    TEXT,
            undone      INTEGER DEFAULT 0,
            duration_ms REAL,
            arm         TEXT DEFAULT 'cmd'
        );

        -- WiFi credentials
        CREATE TABLE IF NOT EXISTS wifi (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ssid      TEXT NOT NULL UNIQUE,
            password  TEXT,
            security  TEXT DEFAULT 'WPA2',
            profile   TEXT DEFAULT 'home',
            last_used TEXT,
            added_at  TEXT DEFAULT (datetime('now'))
        );

        -- Bluetooth devices
        CREATE TABLE IF NOT EXISTS bluetooth (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            mac         TEXT UNIQUE,
            dtype       TEXT DEFAULT 'unknown',
            trusted     INTEGER DEFAULT 0,
            profile     TEXT DEFAULT 'home',
            last_seen   TEXT,
            added_at    TEXT DEFAULT (datetime('now'))
        );

        -- Installed packages (tracked by Friday)
        CREATE TABLE IF NOT EXISTS packages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            manager      TEXT NOT NULL,
            version      TEXT,
            installed_at TEXT DEFAULT (datetime('now'))
        );

        -- Auto-login credentials (browser)
        CREATE TABLE IF NOT EXISTS credentials (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            site       TEXT NOT NULL,
            url_pattern TEXT,
            username   TEXT,
            password   TEXT,
            notes      TEXT,
            added_at   TEXT DEFAULT (datetime('now'))
        );

        -- Browser sessions (recorder)
        CREATE TABLE IF NOT EXISTS browser_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            steps      TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            last_run   TEXT,
            run_count  INTEGER DEFAULT 0
        );

        -- Aliases / snippets
        CREATE TABLE IF NOT EXISTS aliases (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            command    TEXT NOT NULL,
            description TEXT,
            run_count  INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Reminders
        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            text       TEXT NOT NULL,
            due_time   TEXT NOT NULL,
            repeat     TEXT DEFAULT 'none',
            priority   TEXT DEFAULT 'normal',
            done       INTEGER DEFAULT 0,
            snoozed    TEXT,
            escalated  INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Goals
        CREATE TABLE IF NOT EXISTS goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            status      TEXT DEFAULT 'active',
            progress    INTEGER DEFAULT 0,
            steps       TEXT DEFAULT '[]',
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        -- Facts / notes (memory)
        CREATE TABLE IF NOT EXISTS facts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT NOT NULL,
            category   TEXT DEFAULT 'general',
            importance REAL DEFAULT 1.0,
            ts         TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            content    TEXT NOT NULL,
            tags       TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Intent memory / habit learning
        CREATE TABLE IF NOT EXISTS habits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL UNIQUE,
            preference  TEXT NOT NULL,
            confidence  REAL DEFAULT 1.0,
            count       INTEGER DEFAULT 1,
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        -- Process watchers
        CREATE TABLE IF NOT EXISTS watchers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            process     TEXT NOT NULL,
            auto_restart INTEGER DEFAULT 0,
            alert       INTEGER DEFAULT 1,
            active      INTEGER DEFAULT 1,
            added_at    TEXT DEFAULT (datetime('now'))
        );

        -- Cron jobs (managed by Friday)
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            schedule   TEXT NOT NULL,
            command    TEXT NOT NULL,
            active     INTEGER DEFAULT 1,
            last_run   TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Config profiles
        CREATE TABLE IF NOT EXISTS profiles (
            name       TEXT PRIMARY KEY,
            config     TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Key-value preferences
        CREATE TABLE IF NOT EXISTS prefs (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Saved forms (browser)
        CREATE TABLE IF NOT EXISTS saved_forms (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            url_pattern TEXT,
            fields     TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Time tracking
        CREATE TABLE IF NOT EXISTS time_tracking (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task       TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at   TEXT,
            duration_s INTEGER
        );

        -- Code snippets
        CREATE TABLE IF NOT EXISTS snippets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            language   TEXT DEFAULT 'text',
            content    TEXT NOT NULL,
            tags       TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Encrypted passwords (beyond wifi)
        CREATE TABLE IF NOT EXISTS vault (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            label      TEXT NOT NULL UNIQUE,
            username   TEXT,
            password   TEXT,
            url        TEXT,
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Clipboard history
        CREATE TABLE IF NOT EXISTS clipboard (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT NOT NULL,
            dtype      TEXT DEFAULT 'text',
            ts         TEXT DEFAULT (datetime('now'))
        );

        -- Browser command queue (Friday → Extension)
        CREATE TABLE IF NOT EXISTS browser_queue (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            command    TEXT NOT NULL,
            args       TEXT DEFAULT '{}',
            status     TEXT DEFAULT 'pending',
            result     TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_history_ts   ON history(ts DESC);
        CREATE INDEX IF NOT EXISTS idx_history_tool ON history(tool);
        CREATE INDEX IF NOT EXISTS idx_history_arm  ON history(arm);
        CREATE INDEX IF NOT EXISTS idx_facts_cat    ON facts(category);
        CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_time);
        CREATE INDEX IF NOT EXISTS idx_bq_status    ON browser_queue(status);
        """)


# ── History ────────────────────────────────────────────────────────────────────

def log_cmd(user_input, tool, cmd, risk, success, output, undo=None, ms=0, arm="cmd"):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO history(user_input,tool,cmd,risk,success,output,undo_cmd,duration_ms,arm) VALUES(?,?,?,?,?,?,?,?,?)",
            (user_input, tool, cmd, risk, int(success), str(output)[:3000], undo, ms, arm)
        )
        return cur.lastrowid

def get_history(limit=20, arm=None):
    with conn() as c:
        if arm:
            rows = c.execute("SELECT * FROM history WHERE arm=? ORDER BY ts DESC LIMIT ?", (arm, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM history ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

def get_undoable():
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM history WHERE undo_cmd IS NOT NULL AND undone=0 AND success=1 ORDER BY ts DESC LIMIT 10"
        ).fetchall()
        return [dict(r) for r in rows]

def mark_undone(hid):
    with conn() as c:
        c.execute("UPDATE history SET undone=1 WHERE id=?", (hid,))


# ── WiFi ───────────────────────────────────────────────────────────────────────

def save_wifi(ssid, password, security="WPA2", profile="home"):
    with conn() as c:
        c.execute("""INSERT INTO wifi(ssid,password,security,profile) VALUES(?,?,?,?)
                     ON CONFLICT(ssid) DO UPDATE SET password=excluded.password,
                     security=excluded.security, profile=excluded.profile""",
                  (ssid, password, security, profile))

def get_wifi(ssid):
    with conn() as c:
        r = c.execute("SELECT * FROM wifi WHERE ssid=?", (ssid,)).fetchone()
        return dict(r) if r else None

def list_wifi():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM wifi ORDER BY last_used DESC").fetchall()]

def touch_wifi(ssid):
    with conn() as c:
        c.execute("UPDATE wifi SET last_used=datetime('now') WHERE ssid=?", (ssid,))


# ── Bluetooth ──────────────────────────────────────────────────────────────────

def save_bt(name, mac=None, dtype="unknown", trusted=False, profile="home"):
    with conn() as c:
        c.execute("""INSERT INTO bluetooth(name,mac,dtype,trusted,profile,last_seen) VALUES(?,?,?,?,?,datetime('now'))
                     ON CONFLICT(mac) DO UPDATE SET name=excluded.name,dtype=excluded.dtype,
                     trusted=excluded.trusted,last_seen=datetime('now')""",
                  (name, mac, dtype, int(trusted), profile))

def get_bt(name_or_mac):
    with conn() as c:
        r = c.execute("SELECT * FROM bluetooth WHERE mac=? OR LOWER(name) LIKE LOWER(?)",
                      (name_or_mac, f"%{name_or_mac}%")).fetchone()
        return dict(r) if r else None

def list_bt():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM bluetooth ORDER BY last_seen DESC").fetchall()]


# ── Packages ───────────────────────────────────────────────────────────────────

def log_install(name, manager, version=""):
    with conn() as c:
        c.execute("INSERT INTO packages(name,manager,version) VALUES(?,?,?)", (name, manager, version))

def log_uninstall(name, manager):
    with conn() as c:
        c.execute("DELETE FROM packages WHERE LOWER(name)=LOWER(?) AND manager=?", (name, manager))

def list_packages(manager=None):
    with conn() as c:
        if manager:
            return [dict(r) for r in c.execute("SELECT * FROM packages WHERE manager=? ORDER BY installed_at DESC", (manager,)).fetchall()]
        return [dict(r) for r in c.execute("SELECT * FROM packages ORDER BY installed_at DESC LIMIT 50").fetchall()]


# ── Credentials (browser auto-login) ──────────────────────────────────────────

def save_credential(site, url_pattern, username, password, notes=""):
    with conn() as c:
        c.execute("INSERT INTO credentials(site,url_pattern,username,password,notes) VALUES(?,?,?,?,?)",
                  (site, url_pattern, username, password, notes))

def get_credential(site):
    with conn() as c:
        r = c.execute("SELECT * FROM credentials WHERE LOWER(site) LIKE LOWER(?)", (f"%{site}%",)).fetchone()
        return dict(r) if r else None

def list_credentials():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id,site,url_pattern,username,notes,added_at FROM credentials").fetchall()]


# ── Browser sessions ───────────────────────────────────────────────────────────

def save_session(name, steps: list):
    with conn() as c:
        c.execute("""INSERT INTO browser_sessions(name,steps) VALUES(?,?)
                     ON CONFLICT(name) DO UPDATE SET steps=excluded.steps""",
                  (name, json.dumps(steps)))

def get_session(name):
    with conn() as c:
        r = c.execute("SELECT * FROM browser_sessions WHERE name=?", (name,)).fetchone()
        if r:
            d = dict(r)
            d["steps"] = json.loads(d["steps"])
            return d
        return None

def list_sessions():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT name,created_at,last_run,run_count FROM browser_sessions").fetchall()]

def bump_session(name):
    with conn() as c:
        c.execute("UPDATE browser_sessions SET last_run=datetime('now'), run_count=run_count+1 WHERE name=?", (name,))


# ── Aliases ────────────────────────────────────────────────────────────────────

def save_alias(name, command, description=""):
    with conn() as c:
        c.execute("""INSERT INTO aliases(name,command,description) VALUES(?,?,?)
                     ON CONFLICT(name) DO UPDATE SET command=excluded.command,description=excluded.description""",
                  (name, command, description))

def get_alias(name):
    with conn() as c:
        r = c.execute("SELECT * FROM aliases WHERE LOWER(name)=LOWER(?)", (name,)).fetchone()
        return dict(r) if r else None

def list_aliases():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM aliases ORDER BY run_count DESC").fetchall()]

def bump_alias(name):
    with conn() as c:
        c.execute("UPDATE aliases SET run_count=run_count+1 WHERE name=?", (name,))


# ── Reminders ──────────────────────────────────────────────────────────────────

def add_reminder(text, due_time, repeat="none", priority="normal"):
    with conn() as c:
        cur = c.execute("INSERT INTO reminders(text,due_time,repeat,priority) VALUES(?,?,?,?)",
                        (text, due_time, repeat, priority))
        return cur.lastrowid

def get_due_reminders():
    from datetime import datetime as dt
    now = dt.now().isoformat()
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM reminders WHERE done=0 AND due_time<=? ORDER BY priority DESC",
            (now,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_pending_reminders():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM reminders WHERE done=0 ORDER BY due_time").fetchall()]

def complete_reminder(rid, repeat=None):
    from datetime import datetime as dt, timedelta
    with conn() as c:
        r = c.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
        if not r: return
        if r["repeat"] == "daily":
            new_due = (dt.fromisoformat(r["due_time"]) + timedelta(days=1)).isoformat()
            c.execute("UPDATE reminders SET due_time=?,escalated=0 WHERE id=?", (new_due, rid))
        elif r["repeat"] == "weekly":
            new_due = (dt.fromisoformat(r["due_time"]) + timedelta(weeks=1)).isoformat()
            c.execute("UPDATE reminders SET due_time=?,escalated=0 WHERE id=?", (new_due, rid))
        else:
            c.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))

def escalate_reminder(rid):
    with conn() as c:
        c.execute("UPDATE reminders SET escalated=1 WHERE id=?", (rid,))


# ── Goals ──────────────────────────────────────────────────────────────────────

def add_goal(title, description="", steps=None):
    with conn() as c:
        cur = c.execute("INSERT INTO goals(title,description,steps) VALUES(?,?,?)",
                        (title, description, json.dumps(steps or [])))
        return cur.lastrowid

def update_goal(gid, progress=None, status=None):
    with conn() as c:
        if progress is not None:
            c.execute("UPDATE goals SET progress=?,updated_at=datetime('now') WHERE id=?", (progress, gid))
        if status:
            c.execute("UPDATE goals SET status=?,updated_at=datetime('now') WHERE id=?", (status, gid))

def list_goals(status="active"):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM goals WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()]


# ── Facts & Notes ──────────────────────────────────────────────────────────────

def add_fact(content, category="general", importance=1.0):
    with conn() as c:
        c.execute("INSERT INTO facts(content,category,importance) VALUES(?,?,?)", (content, category, importance))

def search_facts(query):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM facts WHERE LOWER(content) LIKE LOWER(?) ORDER BY importance DESC LIMIT 10",
            (f"%{query}%",)
        ).fetchall()]

def list_facts(category=None):
    with conn() as c:
        if category:
            return [dict(r) for r in c.execute("SELECT * FROM facts WHERE category=? ORDER BY importance DESC LIMIT 20", (category,)).fetchall()]
        return [dict(r) for r in c.execute("SELECT * FROM facts ORDER BY importance DESC LIMIT 20").fetchall()]

def add_note(title, content, tags=None):
    with conn() as c:
        c.execute("INSERT INTO notes(title,content,tags) VALUES(?,?,?)", (title, content, json.dumps(tags or [])))

def list_notes():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT 20").fetchall()]

def search_notes(query):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM notes WHERE LOWER(title) LIKE LOWER(?) OR LOWER(content) LIKE LOWER(?)",
            (f"%{query}%", f"%{query}%")
        ).fetchall()]


# ── Intent memory / habits ─────────────────────────────────────────────────────

def learn_habit(action, preference, confidence=1.0):
    with conn() as c:
        c.execute("""INSERT INTO habits(action,preference,confidence,count) VALUES(?,?,?,1)
                     ON CONFLICT(action) DO UPDATE SET preference=excluded.preference,
                     confidence=MIN(1.0, confidence+0.1), count=count+1, updated_at=datetime('now')""",
                  (action, preference, confidence))

def get_habit(action):
    with conn() as c:
        r = c.execute("SELECT * FROM habits WHERE action=?", (action,)).fetchone()
        return dict(r) if r else None

def list_habits():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM habits ORDER BY count DESC").fetchall()]


# ── Watchers ───────────────────────────────────────────────────────────────────

def add_watcher(process, auto_restart=False, alert=True):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO watchers(process,auto_restart,alert) VALUES(?,?,?)",
                  (process, int(auto_restart), int(alert)))

def list_watchers():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM watchers WHERE active=1").fetchall()]

def remove_watcher(process):
    with conn() as c:
        c.execute("UPDATE watchers SET active=0 WHERE process=?", (process,))


# ── Browser queue ──────────────────────────────────────────────────────────────

def queue_browser_cmd(command, args=None):
    with conn() as c:
        cur = c.execute("INSERT INTO browser_queue(command,args) VALUES(?,?)",
                        (command, json.dumps(args or {})))
        return cur.lastrowid

def get_pending_browser_cmds():
    with conn() as c:
        rows = c.execute("SELECT * FROM browser_queue WHERE status='pending' ORDER BY id").fetchall()
        return [dict(r) for r in rows]

def update_browser_cmd(cmd_id, status, result=None):
    with conn() as c:
        c.execute("UPDATE browser_queue SET status=?,result=?,updated_at=datetime('now') WHERE id=?",
                  (status, result, cmd_id))

def get_browser_result(cmd_id, timeout=30):
    """Poll for browser command result."""
    import time
    start = time.time()
    while time.time() - start < timeout:
        with conn() as c:
            r = c.execute("SELECT * FROM browser_queue WHERE id=?", (cmd_id,)).fetchone()
            if r and r["status"] in ("done", "error"):
                return dict(r)
        time.sleep(0.4)
    return {"status": "timeout", "result": "Browser did not respond in time"}


# ── Vault (password manager) ───────────────────────────────────────────────────

def vault_save(label, username, password, url="", notes=""):
    with conn() as c:
        c.execute("""INSERT INTO vault(label,username,password,url,notes) VALUES(?,?,?,?,?)
                     ON CONFLICT(label) DO UPDATE SET username=excluded.username,
                     password=excluded.password,url=excluded.url,notes=excluded.notes""",
                  (label, username, password, url, notes))

def vault_get(label):
    with conn() as c:
        r = c.execute("SELECT * FROM vault WHERE LOWER(label) LIKE LOWER(?)", (f"%{label}%",)).fetchone()
        return dict(r) if r else None

def vault_list():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id,label,username,url,created_at FROM vault").fetchall()]


# ── Snippets ───────────────────────────────────────────────────────────────────

def save_snippet(name, content, language="text", tags=None):
    with conn() as c:
        c.execute("""INSERT INTO snippets(name,language,content,tags) VALUES(?,?,?,?)
                     ON CONFLICT(name) DO UPDATE SET content=excluded.content,language=excluded.language""",
                  (name, language, content, json.dumps(tags or [])))

def get_snippet(name):
    with conn() as c:
        r = c.execute("SELECT * FROM snippets WHERE LOWER(name) LIKE LOWER(?)", (f"%{name}%",)).fetchone()
        return dict(r) if r else None

def list_snippets():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT name,language,tags,created_at FROM snippets").fetchall()]


# ── Clipboard history ──────────────────────────────────────────────────────────

def save_clipboard(content, dtype="text"):
    with conn() as c:
        c.execute("INSERT INTO clipboard(content,dtype) VALUES(?,?)", (content, dtype))
        c.execute("DELETE FROM clipboard WHERE id NOT IN (SELECT id FROM clipboard ORDER BY ts DESC LIMIT 50)")

def list_clipboard(limit=10):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clipboard ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


# ── Prefs ──────────────────────────────────────────────────────────────────────

def set_pref(key, value):
    with conn() as c:
        c.execute("""INSERT INTO prefs(key,value) VALUES(?,?)
                     ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=datetime('now')""",
                  (key, json.dumps(value)))

def get_pref(key, default=None):
    with conn() as c:
        r = c.execute("SELECT value FROM prefs WHERE key=?", (key,)).fetchone()
        if r:
            try: return json.loads(r["value"])
            except: return r["value"]
        return default


# ── Stats ──────────────────────────────────────────────────────────────────────

def db_stats():
    with conn() as c:
        return {
            "commands":      c.execute("SELECT COUNT(*) FROM history").fetchone()[0],
            "success_rate":  "{:.0f}%".format(
                c.execute("SELECT AVG(success)*100 FROM history").fetchone()[0] or 0),
            "wifi_saved":    c.execute("SELECT COUNT(*) FROM wifi").fetchone()[0],
            "bt_devices":    c.execute("SELECT COUNT(*) FROM bluetooth").fetchone()[0],
            "facts":         c.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
            "notes":         c.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
            "reminders":     c.execute("SELECT COUNT(*) FROM reminders WHERE done=0").fetchone()[0],
            "goals":         c.execute("SELECT COUNT(*) FROM goals WHERE status='active'").fetchone()[0],
            "aliases":       c.execute("SELECT COUNT(*) FROM aliases").fetchone()[0],
            "habits_learned":c.execute("SELECT COUNT(*) FROM habits").fetchone()[0],
            "credentials":   c.execute("SELECT COUNT(*) FROM credentials").fetchone()[0],
            "sessions":      c.execute("SELECT COUNT(*) FROM browser_sessions").fetchone()[0],
            "snippets":      c.execute("SELECT COUNT(*) FROM snippets").fetchone()[0],
            "db_path":       str(DB_PATH),
        }
