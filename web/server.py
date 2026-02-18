"""
Friday Flask Bridge
Chrome extension polls this for browser commands.
Also serves the local web dashboard.
"""
import json
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

from db.database import (
    get_pending_browser_cmds, update_browser_cmd,
    db_stats, get_history, list_habits, get_pending_reminders,
    list_goals, list_aliases, list_sessions, list_bt, list_wifi,
)

import logging

app = Flask(__name__)
CORS(app)  # Chrome extension requires this

# Suppress noisy werkzeug access logs for health-check & extension polling
class _NoHealthFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return "GET /health" not in msg and "GET /friday/browser/pending" not in msg

logging.getLogger("werkzeug").addFilter(_NoHealthFilter())

# ── Health ─────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "online", "agent": "Friday AI", "ts": datetime.now().isoformat()})


# ── Browser command queue ──────────────────────────────────────────────────────

@app.route("/friday/browser/pending")
def browser_pending():
    """Extension polls this every 500ms to get commands to execute."""
    cmds = get_pending_browser_cmds()
    if not cmds:
        return jsonify([])
    # Mark all as 'executing'
    for c in cmds:
        update_browser_cmd(c["id"], "executing")
    return jsonify(cmds)


@app.route("/friday/browser/result", methods=["POST"])
def browser_result():
    """Extension posts results back here."""
    data = request.json
    cmd_id = data.get("id")
    status = data.get("status", "done")
    result = data.get("result", "")
    if cmd_id:
        update_browser_cmd(cmd_id, status, json.dumps(result) if not isinstance(result, str) else result)
    return jsonify({"ok": True})


@app.route("/friday/browser/recording_done", methods=["POST"])
def recording_done():
    """Extension sends back recorded session steps."""
    data = request.json
    name = data.get("name","unnamed")
    steps = data.get("steps",[])
    from db.database import save_session
    save_session(name, steps)
    return jsonify({"ok": True, "saved": len(steps)})


# ── FormClaw / JS Automation (from previous system, unified) ──────────────────

# Rate-limit state for /automate
_automate_rate = {"blocked_until": 0}

@app.route("/automate", methods=["POST"])
def automate():
    """Generate JS automation code for a page — browser extension endpoint."""
    import os, re
    from groq import Groq, RateLimitError, BadRequestError

    # Check if we're still in a cooldown window from a prior 429
    now = time.time()
    if now < _automate_rate["blocked_until"]:
        wait = int(_automate_rate["blocked_until"] - now)
        return jsonify({
            "error": f"Rate limit cooldown — try again in {wait}s",
            "ok": False, "retry_after": wait
        }), 429

    data = request.json or {}
    # Truncate HTML aggressively — 8000 chars is plenty for JS generation
    html        = (data.get("html", ""))[:8000]
    instruction = data.get("instruction", "")
    url         = data.get("url", "")

    if not instruction:
        return jsonify({"error": "instruction required", "ok": False}), 400

    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    t0 = time.time()

    SYSP = (
        "You are Friday browser automation. Given page HTML and an instruction, "
        "output ONLY valid JSON: {\"js_code\":\"...\",\"explanation\":\"one sentence\"}\n"
        "js_code rules: pure JS async IIFE, use const sleep=ms=>new Promise(r=>setTimeout(r,ms)), "
        "dispatch input+change events for React/Vue, no alert(), no fetch()."
    )

    try:
        resp = client.chat.completions.create(
            model=os.getenv("MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
            messages=[
                {"role": "system", "content": SYSP},
                {"role": "user",   "content": f"URL:{url}\nINSTRUCTION:{instruction}\nHTML:\n{html}"}
            ],
            max_tokens=1024, temperature=0.1,
        )
    except RateLimitError as e:
        # Parse retry-after from error message if available
        import re as _re
        m = _re.search(r'in (\d+)m(\d+(?:\\.\d+)?)s', str(e))
        wait_secs = 60
        if m:
            wait_secs = int(m.group(1)) * 60 + float(m.group(2))
        _automate_rate["blocked_until"] = time.time() + wait_secs
        return jsonify({
            "error": f"Groq daily token limit reached. Try again in {int(wait_secs)}s.",
            "ok": False, "retry_after": int(wait_secs)
        }), 429
    except BadRequestError as e:
        return jsonify({"error": f"Bad request: {str(e)[:200]}", "ok": False}), 400
    except Exception as e:
        return jsonify({"error": f"LLM error: {str(e)[:200]}", "ok": False}), 500

    raw = resp.choices[0].message.content or ""
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        result = json.loads(raw)
    except Exception:
        m = re.search(r'\{.*"js_code".*\}', raw, re.DOTALL)
        result = json.loads(m.group(0)) if m else {"js_code": "", "explanation": "Parse error"}

    return jsonify({
        **result,
        "ok": True,
        "tokens": resp.usage.total_tokens if resp.usage else 0,
        "duration_ms": round((time.time() - t0) * 1000, 1)
    })


# ── Web Dashboard ──────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Friday AI Dashboard</title>
<meta http-equiv="refresh" content="15">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@500;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#08080f;--surface:#0e0e1a;--border:#1a1a2e;
  --accent:#7c5cfc;--cyan:#00e5ff;--green:#00ff9d;
  --warn:#ffb800;--red:#ff4757;--text:#e8e8f0;--muted:#555570;
}
body{background:var(--bg);color:var(--text);font-family:'Syne',sans-serif;padding:24px;min-height:100vh}
h1{font-size:28px;font-weight:800;background:linear-gradient(90deg,#fff,var(--cyan));
   -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:6px}
.sub{color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:11px;margin-bottom:32px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px}
.card h2{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
         color:var(--muted);margin-bottom:14px}
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.stat{background:rgba(124,92,252,.07);border:1px solid rgba(124,92,252,.15);
      border-radius:10px;padding:12px}
.stat-val{font-size:26px;font-weight:800;color:var(--accent)}
.stat-key{font-size:10px;color:var(--muted);margin-top:2px;font-family:'JetBrains Mono',monospace}
.row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);font-size:12px}
.row:last-child{border-bottom:none}
.tag{background:rgba(0,229,255,.08);color:var(--cyan);border:1px solid rgba(0,229,255,.2);
     padding:2px 7px;border-radius:5px;font-size:10px;font-family:'JetBrains Mono',monospace}
.ok{color:var(--green)} .err{color:var(--red)} .warn{color:var(--warn)}
.bar-wrap{height:6px;background:var(--border);border-radius:3px;flex:1}
.bar{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--cyan))}
code{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--cyan);
     background:rgba(0,229,255,.07);padding:2px 6px;border-radius:4px}
.pill{display:inline-flex;align-items:center;gap:4px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--green);
     box-shadow:0 0 6px var(--green)}
</style>
</head>
<body>
<h1>⚡ Friday AI</h1>
<div class="sub">
  <span class="pill"><span class="dot"></span> Online</span>
  &nbsp;·&nbsp; Dashboard refreshes every 15s &nbsp;·&nbsp; {{ now }}
</div>
<div class="grid">

  <!-- Stats -->
  <div class="card">
    <h2>📊 Overview</h2>
    <div class="stat-grid">
      <div class="stat"><div class="stat-val">{{ stats.commands }}</div><div class="stat-key">Commands</div></div>
      <div class="stat"><div class="stat-val">{{ stats.success_rate }}</div><div class="stat-key">Success Rate</div></div>
      <div class="stat"><div class="stat-val">{{ stats.habits_learned }}</div><div class="stat-key">Habits Learned</div></div>
      <div class="stat"><div class="stat-val">{{ stats.reminders }}</div><div class="stat-key">Reminders</div></div>
      <div class="stat"><div class="stat-val">{{ stats.goals }}</div><div class="stat-key">Active Goals</div></div>
      <div class="stat"><div class="stat-val">{{ stats.sessions }}</div><div class="stat-key">BR Sessions</div></div>
    </div>
  </div>

  <!-- Recent history -->
  <div class="card">
    <h2>🕐 Recent Commands</h2>
    {% for h in history %}
    <div class="row">
      <span class="{{ 'ok' if h.success else 'err' }}">{{ '✓' if h.success else '✗' }}</span>
      <span style="font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace">{{ h.ts[11:16] }}</span>
      <span class="tag">{{ h.arm or 'cmd' }}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ h.user_input[:42] }}</span>
    </div>
    {% endfor %}
  </div>

  <!-- Goals -->
  <div class="card">
    <h2>🎯 Active Goals</h2>
    {% for g in goals %}
    <div class="row" style="flex-direction:column;align-items:flex-start;gap:4px">
      <div style="width:100%;display:flex;justify-content:space-between">
        <span>{{ g.title }}</span><span class="warn">{{ g.progress }}%</span>
      </div>
      <div class="bar-wrap"><div class="bar" style="width:{{ g.progress }}%"></div></div>
    </div>
    {% endfor %}
    {% if not goals %}<div style="color:var(--muted);font-size:12px">No active goals</div>{% endif %}
  </div>

  <!-- Reminders -->
  <div class="card">
    <h2>⏰ Reminders</h2>
    {% for r in reminders %}
    <div class="row">
      <span class="{{ 'err' if r.priority=='high' else 'warn' if r.priority=='normal' else 'ok' }}">●</span>
      <span style="flex:1">{{ r.text[:38] }}</span>
      <code>{{ r.due_time[11:16] }}</code>
    </div>
    {% endfor %}
    {% if not reminders %}<div style="color:var(--muted);font-size:12px">No reminders</div>{% endif %}
  </div>

  <!-- Habits -->
  <div class="card">
    <h2>🧠 Learned Habits</h2>
    {% for h in habits %}
    <div class="row">
      <span style="flex:1;color:var(--muted)">{{ h.action }}</span>
      <code>{{ h.preference }}</code>
      <span style="color:var(--muted);font-size:10px">×{{ h.count }}</span>
    </div>
    {% endfor %}
    {% if not habits %}<div style="color:var(--muted);font-size:12px">No habits learned yet</div>{% endif %}
  </div>

  <!-- DB stats -->
  <div class="card">
    <h2>🗄 Database</h2>
    {% for k,v in stats.items() %}
    {% if k != 'db_path' %}
    <div class="row">
      <span style="flex:1;color:var(--muted)">{{ k.replace('_',' ') }}</span>
      <code>{{ v }}</code>
    </div>
    {% endif %}
    {% endfor %}
    <div class="row" style="margin-top:4px">
      <span style="color:var(--muted);font-size:10px;font-family:'JetBrains Mono',monospace">{{ stats.db_path }}</span>
    </div>
  </div>

</div>
</body>
</html>"""

@app.route("/")
@app.route("/dashboard")
def dashboard():
    stats    = db_stats()
    history  = get_history(8)
    habits   = list_habits()[:8]
    reminders = get_pending_reminders()[:6]
    goals    = list_goals("active")[:5]
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(DASHBOARD_HTML,
        stats=stats, history=history, habits=habits,
        reminders=reminders, goals=goals, now=now)


# ── Chat API (used by popup system panel and external clients) ─────────────────

_agent_ref = None   # set from main.py after boot

def set_agent(agent):
    global _agent_ref
    _agent_ref = agent


@app.route("/friday/chat", methods=["POST"])
def chat_endpoint():
    """Single chat turn — popup system panel uses this."""
    data = request.json or {}
    msg  = (data.get("message") or data.get("text") or "").strip()
    if not msg:
        return jsonify({"error": "empty message"}), 400
    if _agent_ref is None:
        return jsonify({"error": "Agent not ready"}), 503
    try:
        reply = _agent_ref.chat(msg)
        return jsonify({"reply": reply, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e), "ok": False}), 500


# ── Data API (popup memory panel) ──────────────────────────────────────────────

@app.route("/friday/data/reminders")
def data_reminders():
    from db.database import get_pending_reminders
    return jsonify({"data": get_pending_reminders()[:10]})

@app.route("/friday/data/goals")
def data_goals():
    return jsonify({"data": list_goals("active")[:10]})

@app.route("/friday/data/habits")
def data_habits():
    return jsonify({"data": list_habits()[:15]})

@app.route("/friday/data/history")
def data_history():
    limit = int(request.args.get("limit", 20))
    return jsonify({"data": get_history(limit)})

@app.route("/friday/data/stats")
def data_stats():
    return jsonify(db_stats())

@app.route("/friday/data/aliases")
def data_aliases():
    return jsonify({"data": list_aliases()})

@app.route("/friday/data/sessions")
def data_sessions():
    return jsonify({"data": list_sessions()})

@app.route("/friday/data/wifi")
def data_wifi():
    return jsonify({"data": list_wifi()})

@app.route("/friday/data/bluetooth")
def data_bluetooth():
    return jsonify({"data": list_bt()})


# ── Run ────────────────────────────────────────────────────────────────────────

def run_server(host="127.0.0.1", port=7723):
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


def start_server_thread(host="127.0.0.1", port=7723):
    t = threading.Thread(target=run_server, args=(host, port), daemon=True)
    t.start()
    return t
