# Friday AI — Skill Creation Template

**Drop any `.py` file in `skills/` folder and Friday auto-loads it.**

---

## Basic Structure

Every skill file must export two things:

```python
SKILL_TOOLS = [...]      # List of tool definitions (JSON schema)
SKILL_HANDLERS = {...}   # Dict mapping tool names to functions
```

---

## Minimal Example

```python
# skills/hello_skill.py

def greet(name: str):
    return type('R', (), {
        'ok': True,
        'out': f'Hello, {name}!',
        'cmd': 'greet'
    })()

SKILL_TOOLS = [{
    "type": "function",
    "function": {
        "name": "greet",
        "description": "Greet someone by name",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's name"}
            },
            "required": ["name"]
        }
    }
}]

SKILL_HANDLERS = {
    "greet": lambda args: greet(args["name"])
}
```

Now users can say: **"Friday, greet Alice"** and Friday will call your skill.

---

## Return Format

Skills must return an object with:
- `ok` (bool): Success status
- `out` (str): Output text shown to user
- `cmd` (str): Command name (for logging)
- `undo` (str, optional): Undo command

```python
from dataclasses import dataclass

@dataclass
class R:
    ok: bool
    out: str
    cmd: str = ""
    undo: str = None
```

---

## Accessing Friday's Tools

Skills can call Friday's existing tools:

```python
# Inside your skill function
from ops.system_ops import connect_wifi, set_volume
from tools.web_tools import web_search
from db.database import save_wifi, remember_fact

def my_automation():
    # Call Friday's tools
    connect_wifi("HomeNet")
    set_volume(50)
    results = web_search("latest news")
    remember_fact("Automation ran successfully")
    return R(True, "Done", "my_automation")
```

---

## Accessing Friday's Database

```python
from db.database import (
    conn,           # Database connection context manager
    add_fact,       # Save a fact
    add_reminder,   # Create reminder
    save_wifi,      # Save WiFi credentials
    log_cmd,        # Log command to history
)

def save_data(key, value):
    with conn() as c:
        c.execute("INSERT INTO my_table(key, value) VALUES(?,?)", (key, value))
    return R(True, f"Saved {key}={value}", "save_data")
```

---

## PyAutoGUI Recorder Skill Example

```python
# skills/recorder.py
import pyautogui
import json
from pathlib import Path
from datetime import datetime
from pynput import mouse, keyboard
from dataclasses import dataclass

@dataclass
class R:
    ok: bool; out: str; cmd: str = ""

# State
_recording = False
_actions = []
_listener_mouse = None
_listener_kbd = None

def start_recording(name: str):
    global _recording, _actions, _listener_mouse, _listener_kbd
    
    if _recording:
        return R(False, "Already recording", "start_recording")
    
    _recording = True
    _actions = []
    
    # Mouse listener
    def on_click(x, y, button, pressed):
        if pressed:
            _actions.append({
                "type": "click",
                "x": x, "y": y,
                "button": str(button),
                "time": datetime.now().isoformat()
            })
    
    # Keyboard listener
    def on_key(key):
        try:
            char = key.char
        except AttributeError:
            char = str(key)
        _actions.append({
            "type": "key",
            "key": char,
            "time": datetime.now().isoformat()
        })
    
    _listener_mouse = mouse.Listener(on_click=on_click)
    _listener_kbd = keyboard.Listener(on_press=on_key)
    _listener_mouse.start()
    _listener_kbd.start()
    
    return R(True, f"Recording '{name}'. Say 'stop recording' to finish.", "start_recording")


def stop_recording():
    global _recording, _listener_mouse, _listener_kbd
    
    if not _recording:
        return R(False, "Not recording", "stop_recording")
    
    _recording = False
    if _listener_mouse: _listener_mouse.stop()
    if _listener_kbd: _listener_kbd.stop()
    
    # Save to file
    recordings_dir = Path.home() / ".friday" / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = recordings_dir / filename
    
    with open(filepath, "w") as f:
        json.dump(_actions, f, indent=2)
    
    return R(True, f"Recorded {len(_actions)} actions → {filepath}", "stop_recording")


def replay_recording(filepath: str):
    import time
    
    path = Path(filepath).expanduser()
    if not path.exists():
        # Try recordings dir
        path = Path.home() / ".friday" / "recordings" / filepath
        if not path.exists():
            return R(False, f"Recording not found: {filepath}", "replay")
    
    with open(path) as f:
        actions = json.load(f)
    
    # Replay
    for i, action in enumerate(actions):
        if action["type"] == "click":
            pyautogui.click(action["x"], action["y"])
        elif action["type"] == "key":
            pyautogui.press(action["key"])
        
        # Wait a bit between actions
        if i < len(actions) - 1:
            time.sleep(0.3)
    
    return R(True, f"Replayed {len(actions)} actions", "replay")


def list_recordings():
    recordings_dir = Path.home() / ".friday" / "recordings"
    if not recordings_dir.exists():
        return R(True, "No recordings yet", "list_recordings")
    
    files = list(recordings_dir.glob("*.json"))
    if not files:
        return R(True, "No recordings yet", "list_recordings")
    
    lines = [f"  {f.name}" for f in sorted(files, reverse=True)[:10]]
    return R(True, "Recordings:\n" + "\n".join(lines), "list_recordings")


# Export to Friday
SKILL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "start_recording",
            "description": "Start recording mouse clicks and keyboard input",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Recording session name"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_recording",
            "description": "Stop recording and save to file",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replay_recording",
            "description": "Replay a saved recording",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Recording file path or name"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_recordings",
            "description": "List all saved recordings",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

SKILL_HANDLERS = {
    "start_recording": lambda a: start_recording(a["name"]),
    "stop_recording":  lambda a: stop_recording(),
    "replay_recording": lambda a: replay_recording(a["filepath"]),
    "list_recordings":  lambda a: list_recordings(),
}
```

**Dependencies for this skill:**
```bash
pip install pyautogui pynput
```

**Usage:**
```
Friday, start recording login_flow
[perform actions...]
Friday, stop recording
Friday, replay recording recording_20260217_143022.json
Friday, list recordings
```

---

## API Integration Skill Example

```python
# skills/github_skill.py
import requests
from dataclasses import dataclass

@dataclass
class R:
    ok: bool; out: str; cmd: str = ""

def get_github_repos(username: str):
    try:
        r = requests.get(f"https://api.github.com/users/{username}/repos", timeout=10)
        r.raise_for_status()
        repos = r.json()
        
        lines = [f"GitHub repos for @{username}:\n"]
        for repo in repos[:10]:
            stars = repo.get("stargazers_count", 0)
            lines.append(f"  ⭐ {stars:4d}  {repo['name']}")
        
        return R(True, "\n".join(lines), "get_github_repos")
    except Exception as e:
        return R(False, f"Error: {e}", "get_github_repos")

SKILL_TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_github_repos",
        "description": "Get a user's GitHub repositories",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "GitHub username"}
            },
            "required": ["username"]
        }
    }
}]

SKILL_HANDLERS = {
    "get_github_repos": lambda a: get_github_repos(a["username"])
}
```

---

## Complex Multi-Tool Skill Example

```python
# skills/backup_skill.py
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

@dataclass
class R:
    ok: bool; out: str; cmd: str = ""; undo: str = None

def backup_project(project_path: str, backup_location: str = None):
    """Backup a project folder with timestamp."""
    src = Path(project_path).expanduser()
    if not src.exists():
        return R(False, f"Project not found: {project_path}", "backup_project")
    
    # Default backup location
    if not backup_location:
        backup_location = str(Path.home() / "Backups")
    
    dest_dir = Path(backup_location)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{src.name}_backup_{timestamp}"
    dest = dest_dir / backup_name
    
    try:
        shutil.copytree(src, dest)
        size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / (1024*1024)
        
        # Save to Friday's database
        from db.database import add_fact
        add_fact(f"Backed up {src.name} → {dest}", "backup", importance=1.5)
        
        return R(True, 
                 f"✓ Backed up {src.name}\n  → {dest}\n  Size: {size_mb:.1f} MB",
                 "backup_project",
                 undo=f"rm -rf '{dest}'")
    except Exception as e:
        return R(False, f"Backup failed: {e}", "backup_project")

def restore_backup(backup_path: str, restore_location: str):
    """Restore a backup to specified location."""
    src = Path(backup_path).expanduser()
    dest = Path(restore_location).expanduser()
    
    if not src.exists():
        return R(False, f"Backup not found: {backup_path}", "restore_backup")
    
    if dest.exists():
        return R(False, f"Destination already exists: {restore_location}", "restore_backup")
    
    try:
        shutil.copytree(src, dest)
        return R(True, f"✓ Restored {src.name} → {dest}", "restore_backup")
    except Exception as e:
        return R(False, f"Restore failed: {e}", "restore_backup")

def list_backups(backup_location: str = None):
    """List all backups."""
    if not backup_location:
        backup_location = str(Path.home() / "Backups")
    
    backup_dir = Path(backup_location)
    if not backup_dir.exists():
        return R(True, "No backups found", "list_backups")
    
    backups = [d for d in backup_dir.iterdir() if d.is_dir() and "_backup_" in d.name]
    if not backups:
        return R(True, "No backups found", "list_backups")
    
    lines = ["Backups:\n"]
    for b in sorted(backups, reverse=True)[:15]:
        size_mb = sum(f.stat().st_size for f in b.rglob("*") if f.is_file()) / (1024*1024)
        lines.append(f"  📦 {b.name}  ({size_mb:.1f} MB)")
    
    return R(True, "\n".join(lines), "list_backups")

SKILL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "backup_project",
            "description": "Backup a project folder with timestamp",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "description": "Path to project folder"},
                    "backup_location": {"type": "string", "description": "Optional backup location (default: ~/Backups)"}
                },
                "required": ["project_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "restore_backup",
            "description": "Restore a backup to a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "backup_path": {"type": "string", "description": "Path to backup folder"},
                    "restore_location": {"type": "string", "description": "Where to restore"}
                },
                "required": ["backup_path", "restore_location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_backups",
            "description": "List all backups",
            "parameters": {
                "type": "object",
                "properties": {
                    "backup_location": {"type": "string", "description": "Backup location (default: ~/Backups)"}
                }
            }
        }
    }
]

SKILL_HANDLERS = {
    "backup_project":  lambda a: backup_project(a["project_path"], a.get("backup_location")),
    "restore_backup":  lambda a: restore_backup(a["backup_path"], a["restore_location"]),
    "list_backups":    lambda a: list_backups(a.get("backup_location")),
}
```

---

## Parameter Types Reference

```python
"parameters": {
    "type": "object",
    "properties": {
        "text":     {"type": "string",  "description": "Text input"},
        "count":    {"type": "integer", "description": "Number"},
        "ratio":    {"type": "number",  "description": "Float"},
        "enabled":  {"type": "boolean", "description": "True/False"},
        "items":    {"type": "array",   "items": {"type": "string"}},
        "config":   {"type": "object",  "description": "JSON object"},
    },
    "required": ["text", "count"]  # Required parameters
}
```

---

## Best Practices

1. **Error handling**: Always use try/except, return `R(False, error_msg, ...)`
2. **Import locally**: Import inside functions if heavy dependencies
3. **Validate inputs**: Check paths exist, values in range, etc.
4. **Logging**: Use `from db.database import log_cmd` to log actions
5. **Undo support**: Return undo commands when possible
6. **Clear descriptions**: Tool descriptions help Friday understand when to use your skill
7. **Dependencies**: Document any `pip install` requirements in comments

---

## Testing Your Skill

1. Save skill to `skills/my_skill.py`
2. Restart Friday: `python main.py`
3. Check load: Friday logs "Loaded skill: my_skill (X tools)"
4. Test: "Friday, [your command]"
5. Debug: Check `~/.friday/friday.db` history table

---

## Skill Can Call Friday's Agent

```python
# Advanced: skills can ask Friday to do things
from core.agent import FridayAgent

# This requires passing agent reference to skills
# (not yet implemented, but coming soon)

def my_complex_automation():
    # Pseudo-code for future feature
    agent.chat("connect wifi HomeNet")
    agent.chat("open chrome and navigate to github.com")
    return R(True, "Automation complete", "my_automation")
```

---

**Questions?** Ask Friday: `skill help` or `skill examples`

**Share your skills:** Export your `.py` file and share with others!
