# ⚡ Friday AI

**Unified AI system agent — CMD control + browser automation + intelligence.**

Friday combines three systems into one:
- **CMD Arm** — controls your computer (WiFi, Bluetooth, files, packages, services, Docker, SSH, cron, etc.)
- **Browser Arm** — controls Chrome via extension (click, fill, scrape, record, replay, auto-login)
- **Intelligence** — intent memory, habit learning, proactive reminders, multi-step planning

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> Optional but recommended: `pip install psutil` for CPU/RAM stats

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

Get a free API key at [console.groq.com](https://console.groq.com).

### 3. Run

```bash
python main.py
```

Friday starts the REPL, Flask bridge (port 7723), scheduler, and all background services.

---

## Chrome Extension Setup

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The Friday ⚡ icon appears in your toolbar

> The extension polls `http://localhost:7723` for commands. Friday must be running.

---

## What You Can Say

### System Control
```
volume 75
mute
connect wifi HomeNet
save wifi HomeNet mypassword123
connect bluetooth AirPods
install numpy
install apt ffmpeg
move ~/downloads/file.pdf ~/docs/
copy ~/docs/ ~/backup/docs/
delete ~/temp/old.log
list ~/projects/
search *.py in ~/code modified in last 7 days
archive ~/project output=project.zip
service nginx restart
docker ps
kill port 3000
ssh user@192.168.1.100
cron add "0 8 * * *" "python ~/morning.py" name=morning
brightness 60
lock
sysinfo
disk usage
get ip
scan network
speed test
```

### Browser Control (extension must be active)
```
navigate to github.com
click the login button
fill the form with name=John email=john@test.com
fill form with test data
read this page
what is the main topic of this page?
extract the table on this page
get all links
scroll down 1000 pixels
close all youtube tabs
open new tab with google.com
record session checkout
stop recording
replay session checkout
save login github user@me.com mypassword
auto login github
```

### Web & Information
```
search latest AI news
weather Tokyo
weather New York tomorrow
stock AAPL
stock TSLA
100 USD to EUR
50 km to miles
calculate 2^32 / 1024
wikipedia quantum computing
fetch https://api.github.com/repos/anthropics/anthropic-sdk-python
test api GET https://jsonplaceholder.typicode.com/posts/1
start server in ~/myapp on port 8080
```

### Memory & Productivity
```
remember my API key is sk-xxx
remember I prefer dark mode
recall api key
remind me to submit report in 2 hours
remind me to exercise tomorrow morning
remind me every day at 9am to check emails
create goal: learn Rust by end of month
goal 1 progress 30
show goals
save note "Meeting notes" "Discussed Q4 roadmap"
show notes
find note roadmap
pomodoro start deep work
pomodoro status
alias deploy "git add . && git commit -m 'update' && git push"
run alias deploy
save snippet fibonacci_py "def fib(n): ..."
vault save github myuser mypassword
vault get github
habits
history
db stats
undo
```

### Developer Tools
```
python3 version check
run python "import sys; print(sys.version)"
create venv ~/projects/myapp/.venv
list venvs
read .env
set OPENAI_KEY=sk-xxx in .env
port 8080 what's using it?
kill port 8080
battery
uptime
ping 8.8.8.8
public ip
top cpu processes
open ports
dns lookup anthropic.com
```

---

## Dashboard

Open `http://localhost:7723/dashboard` while Friday is running to see:
- Live command history
- Active goals with progress bars
- Pending reminders
- Learned habits
- Database stats

---

## Proactive Features

Friday runs background services automatically:

| Service | What it does |
|---------|-------------|
| Morning briefing | Weather + reminders + goals digest at 08:00 |
| Evening summary | Daily command count at 21:00 |
| Reminder polling | Checks due reminders every 60s, escalates missed ones |
| Anomaly watcher | Alerts if CPU/RAM/Disk exceeds threshold |
| Process watcher | Monitors processes, optionally auto-restarts them |

Configure in `.env`:
```
MORNING_BRIEFING_TIME=08:00
CPU_ALERT_THRESHOLD=90
PROCESS_WATCH_INTERVAL=30
```

---

## Adding Skills (Enhanced Plugin System)

**Friday now features a dynamic skill system with auto-reload!**

### Quick Start: Add a Custom Skill

1. **Get the template:**
   ```
   Friday, show skill template
   ```
   This opens `SKILL_TEMPLATE.md` with complete examples.

2. **Create your skill:**
   - Copy template to Claude.ai or another LLM
   - Ask: "Write me a PyAutoGUI recorder skill that records clicks and replays them"
   - Claude generates Python code following Friday's skill format

3. **Install the skill:**
   - Save generated code as `skills/my_recorder.py`
   - Friday **auto-detects** the new file in ~2 seconds
   - No restart needed! Skills load dynamically

4. **Use your skill:**
   ```
   Friday, start recording my_workflow
   [perform actions...]
   Friday, stop recording
   Friday, replay recording my_workflow
   ```

### Skill Template Structure

Every skill needs:

```python
# skills/my_skill.py

SKILL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "my_tool",
            "description": "What this tool does",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg": {"type": "string", "description": "input"}
                },
                "required": ["arg"]
            }
        }
    }
]

SKILL_HANDLERS = {
    "my_tool": lambda args: my_function(args["arg"])
}
```

### Skills Can Access Friday's Powers

Your skills can call Friday's existing tools:

```python
from ops.system_ops import connect_wifi, set_volume
from tools.web_tools import web_search
from db.database import add_fact, save_wifi

def my_automation():
    connect_wifi("HomeNet")      # Use Friday's WiFi
    results = web_search("news")  # Use Friday's search
    add_fact("Task completed")    # Save to Friday's DB
    return R(True, "Done", "my_automation")
```

### Skill Management Commands

```
skill template          # Open template with examples
open skill folder       # Open skills/ in file manager
list skills             # Show all loaded skills
reload skills           # Force reload (auto-reloads anyway)
```

### Example Skills in Template

The template includes complete working examples:

1. **PyAutoGUI Recorder** — Record mouse/keyboard, replay actions
2. **GitHub API Integration** — Fetch repos, stars, etc.
3. **Backup System** — Automated project backups with restore
4. **Custom Automation** — Multi-step workflows

### Auto-Reload Feature

- Drop any `.py` file into `skills/` folder
- Friday detects it within 2 seconds
- Skills load automatically
- See notification: "Skills reloaded — X tools available"
- No restart needed!

---

## Browser Extension Skills

**NEW:** Control ANY website with Friday using JavaScript skills!

### Quick Start

1. **Get template:**
   ```
   Friday, show extension skill template
   ```
   Opens `EXTENSION_SKILL_TEMPLATE.md` with complete examples

2. **Create skill:**
   - Upload template to Claude.ai
   - Ask: "Write me a Spotify controller skill"
   - Get JavaScript code following template

3. **Install:**
   - Save as `extension/skills/spotify_skill.js`
   - Reload extension in Chrome
   - Ready to use immediately!

4. **Use:**
   ```
   Friday, youtube play
   Friday, youtube pause
   Friday, youtube volume 50
   ```

### Built-in: YouTube Controller

Friday includes a complete YouTube controller:

```bash
youtube play / pause / resume / stop
youtube mute / unmute
youtube volume 50          # 0-100
youtube speed 1.5          # 0.25-2.0
youtube skip 10            # skip forward
youtube back 10            # skip backward
youtube restart
youtube fullscreen
youtube info               # current status
youtube next               # next video
youtube like / dislike
youtube subscribe
```

### Example: User Creates Spotify Skill

**User → Claude.ai:**
```
Here's Friday's extension skill template: [paste EXTENSION_SKILL_TEMPLATE.md]

Write me a skill that controls Spotify web player:
- play/pause/next/previous
- shuffle on/off
- show current song
```

**Claude generates:** `spotify_skill.js`

**User:** Saves to `extension/skills/spotify_skill.js`, reloads extension

**User:** "Friday, spotify play" → ▶ Music plays!

### Works on ANY Website

Extension skills can control:
- **Streaming**: YouTube, Netflix, Spotify, Twitch
- **Social**: Twitter/X, LinkedIn, Facebook, Instagram
- **Productivity**: Gmail, Notion, Trello, Slack
- **Shopping**: Amazon, eBay (add to cart, checkout)
- **Any site with a DOM!**

Skills run JavaScript directly in the browser with full access to:
- Page elements
- Video/audio players
- Forms and inputs
- localStorage/cookies
- Any web API

### Template Includes 5 Complete Examples

1. **YouTube** — Complete video controller (built-in)
2. **Spotify** — Music player control
3. **Gmail** — Compose, search, archive, delete
4. **Twitter/X** — Post, like, retweet
5. **Page Notes** — Save notes on any page (works everywhere)

---

## Telegram (Optional)

Add to `.env`:
```
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Then control Friday from anywhere via Telegram messages.

---

## Risk Levels

Every operation is classified before execution:

| Level | Color | Behavior |
|-------|-------|----------|
| `SAFE` | — | Runs instantly (read-only) |
| `RECOVERABLE` | Yellow | Runs + logged with undo command |
| `DANGEROUS` | Red | Requires `y/n` confirmation |

---

## File Structure

```
friday-ai/
├── main.py                    ← Single entry point
├── requirements.txt
├── .env.example
├── core/
│   ├── agent.py               ← Master brain (60+ tools, Groq Llama 4 Scout)
│   ├── risk.py                ← Risk classifier
│   ├── planner.py             ← Multi-step task planner
│   └── scheduler.py           ← Proactive briefings + reminder escalation
├── db/
│   └── database.py            ← Unified SQLite (20 tables)
├── memory/
│   └── memory.py              ← Facts, notes, goals, reminders, habit learning
├── ops/
│   └── system_ops.py          ← All CMD operations
├── tools/
│   ├── browser_tools.py       ← Browser control client
│   ├── web_tools.py           ← Search, weather, stocks, calc, etc.
│   └── notifier.py            ← Desktop notifications + anomaly watcher
├── web/
│   └── server.py              ← Flask bridge + dashboard
├── skills/
│   ├── registry.py            ← Plugin loader
│   └── infotools.py           ← Battery, ping, ports, DNS, traceroute
├── messaging/
│   └── telegram.py            ← Optional Telegram bot
└── extension/                 ← Chrome Extension
    ├── manifest.json
    ├── icons/
    └── src/
        ├── background.js      ← Service worker
        ├── content.js         ← DOM execution engine
        ├── popup.html         ← Extension UI
        └── popup.js           ← Extension logic
```

---

## Requirements

- Python 3.10+
- Groq API key (free tier works)
- Chrome (for browser arm)
- Linux / macOS / Windows (most features work cross-platform)

---

*Friday AI — built to work for you.*
