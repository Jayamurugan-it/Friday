"""
Friday Browser Tools — CMD-side client
Sends commands to Flask server → Chrome extension executes them.
"""
import time, json
from dataclasses import dataclass
from typing import Optional
from db.database import (
    queue_browser_cmd, get_browser_result, update_browser_cmd,
    save_session, get_session, list_sessions, bump_session,
    get_credential, save_credential, list_credentials,
    get_pref,
)

# Deferred — DB must be initialized before reading prefs
_BROWSER_TIMEOUT: int = 0

def _get_timeout() -> int:
    global _BROWSER_TIMEOUT
    if not _BROWSER_TIMEOUT:
        _BROWSER_TIMEOUT = int(get_pref("browser_timeout", 30) or 30)
    return _BROWSER_TIMEOUT

@dataclass
class R:
    ok: bool; out: str; cmd: str = ""


def _exec(command: str, args: dict = None, timeout: int = None) -> R:
    """Queue a browser command and wait for result."""
    t = timeout or _get_timeout()
    cmd_id = queue_browser_cmd(command, args or {})
    result = get_browser_result(cmd_id, timeout=t)
    if result["status"] == "timeout":
        return R(False, "⚠ Browser extension did not respond. Is Friday extension active in Chrome?", command)
    ok = result["status"] == "done"
    out = result.get("result","(no output)")
    try: out = json.loads(out) if isinstance(out, str) and out.startswith("{") else out
    except Exception: pass
    if isinstance(out, dict):
        out = out.get("text") or out.get("message") or json.dumps(out, indent=2)
    return R(ok, str(out), command)


# ════════════ NAVIGATION ════════════

def navigate(url):
    if not url.startswith("http"): url = "https://" + url
    return _exec("navigate", {"url": url}, timeout=15)

def go_back():    return _exec("go_back")
def go_forward(): return _exec("go_forward")
def reload():     return _exec("reload")
def get_url():    return _exec("get_url")
def get_title():  return _exec("get_title")


# ════════════ DOM INTERACTION ════════════

def click(selector: str = None, text: str = None, index: int = 0):
    return _exec("click", {"selector": selector, "text": text, "index": index})

def fill_input(selector: str, value: str, clear_first: bool = True):
    return _exec("fill_input", {"selector": selector, "value": value, "clear_first": clear_first})

def fill_form(fields: dict):
    """Fill multiple fields at once. fields = {selector: value}"""
    return _exec("fill_form", {"fields": fields})

def select_option(selector: str, value: str = None, text: str = None):
    return _exec("select_option", {"selector": selector, "value": value, "text": text})

def check_box(selector: str, checked: bool = True):
    return _exec("check_box", {"selector": selector, "checked": checked})

def scroll(direction: str = "down", amount: int = 500, selector: str = None):
    return _exec("scroll", {"direction": direction, "amount": amount, "selector": selector})

def hover(selector: str):
    return _exec("hover", {"selector": selector})

def press_key(key: str, selector: str = None):
    return _exec("press_key", {"key": key, "selector": selector})

def wait_for(selector: str, timeout_ms: int = 5000):
    return _exec("wait_for", {"selector": selector, "timeout_ms": timeout_ms})


# ════════════ PAGE READING ════════════

def get_text(selector: str = None):
    return _exec("get_text", {"selector": selector})

def get_html(selector: str = None, outer: bool = False):
    return _exec("get_html", {"selector": selector, "outer": outer})

def read_page():
    """Extract all readable text from current page — for Q&A."""
    return _exec("read_page", {}, timeout=20)

def extract_table(selector: str = None, index: int = 0):
    return _exec("extract_table", {"selector": selector, "index": index})

def find_element(description: str):
    """Ask Friday to find element by human description using heuristics."""
    return _exec("find_element", {"description": description})

def get_links(selector: str = None):
    return _exec("get_links", {"selector": selector})

def get_form_fields():
    return _exec("get_form_fields", {})


# ════════════ TABS ════════════

def get_tabs():    return _exec("get_tabs")
def open_tab(url): return _exec("open_tab", {"url": url})
def close_tab(index: int = None): return _exec("close_tab", {"index": index})
def focus_tab(index: int): return _exec("focus_tab", {"index": index})
def close_other_tabs(): return _exec("close_other_tabs")

def find_tab(query: str):
    return _exec("find_tab", {"query": query})

def close_tabs_by_domain(domain: str):
    return _exec("close_tabs_by_domain", {"domain": domain})


# ════════════ STORAGE & COOKIES ════════════

def get_cookies(domain: str = None):
    return _exec("get_cookies", {"domain": domain})

def get_storage(storage_type: str = "local"):
    return _exec("get_storage", {"type": storage_type})

def trigger_download(url: str):
    return _exec("trigger_download", {"url": url})


# ════════════ JS INJECTION ════════════

def run_js(code: str):
    """Legacy: kept for backward compat. Use dom_op for CSP-safe ops."""
    return _exec("run_js", {"code": code})


def dom_op(op: str, value: str = "") -> R:
    """
    Execute a pre-defined DOM operation — CSP-safe, no eval/new Function.
    Ops: video_play|video_pause|video_toggle|video_mute|video_unmute|
         video_seek|video_speed|video_volume|video_info|
         scroll_down|scroll_up|scroll_top|scroll_bottom|
         page_title|page_url|page_text|click_el|focus_el|open_url|reload_page
    value: optional param (seconds, rate 0-2, level 0-100, selector, url)
    """
    return _exec("dom_op", {"op": op, "value": str(value)})


# ════════════ AUTO-LOGIN ════════════

def auto_login(site: str):
    cred = get_credential(site)
    if not cred:
        return R(False, f"No credentials stored for '{site}'. Use: friday save login {site} user pass")
    url = cred.get("url_pattern","")
    fields = {"email,username,user,login": cred["username"],
              "password,pass,pwd":         cred["password"]}
    result = _exec("auto_login", {"url": url, "fields": fields})
    return R(result.ok, f"Logged into {site}: {result.out}", "auto_login")

def save_login(site: str, username: str, password: str, url_pattern: str = ""):
    save_credential(site, url_pattern, username, password)
    return R(True, f"Login saved for '{site}'", "db")

def list_logins():
    creds = list_credentials()
    if not creds: return R(True, "No logins stored", "db")
    lines = [f"  {c['site']:<25} {c['username']}" for c in creds]
    return R(True, "Saved logins:\n" + "\n".join(lines), "db")


# ════════════ SESSION RECORDER ════════════

def start_recording(name: str):
    return _exec("start_recording", {"name": name})

def stop_recording():
    result = _exec("stop_recording", {})
    return result

def save_recorded_session(name: str, steps: list):
    save_session(name, steps)
    return R(True, f"Session '{name}' saved ({len(steps)} steps)", "db")

def replay_session(name: str):
    session = get_session(name)
    if not session:
        return R(False, f"Session '{name}' not found", "db")
    result = _exec("replay_session", {"steps": session["steps"]}, timeout=60)
    if result.ok: bump_session(name)
    return result

def list_sessions_info():
    sessions = list_sessions()
    if not sessions: return R(True, "No sessions saved", "db")
    lines = [f"  {s['name']:<25} runs:{s['run_count']}  last:{(s['last_run'] or 'never')[:10]}" for s in sessions]
    return R(True, "Browser sessions:\n" + "\n".join(lines), "db")


# ════════════ FORM SAVER ════════════

def save_form(name: str):
    """Save all values from current page's form."""
    result = _exec("get_form_values", {})
    if not result.ok: return result
    from db.database import conn
    with conn() as c:
        c.execute("""INSERT INTO saved_forms(name,fields) VALUES(?,?)
                     ON CONFLICT(name) DO UPDATE SET fields=excluded.fields""",
                  (name, result.out))
    return R(True, f"Form '{name}' saved", "db")

def fill_saved_form(name: str):
    from db.database import conn
    with conn() as c:
        r = c.execute("SELECT * FROM saved_forms WHERE name=?", (name,)).fetchone()
    if not r: return R(False, f"Form '{name}' not found", "db")
    return _exec("fill_form_values", {"fields": r["fields"]})


# ════════════ PAGE Q&A ════════════

def ask_about_page(question: str) -> R:
    """Read current page text, ask LLM about it. Returns answer."""
    page = read_page()
    if not page.ok: return R(False, f"Could not read page: {page.out}")
    # This result is passed back to the agent who then answers using LLM
    return R(True, f"PAGE_CONTENT_FOR_QA::{page.out[:6000]}::QUESTION::{question}", "page_qa")


# ════════════ EXTENSION SKILLS ════════════

def extension_skill(skill_name: str, command_name: str, **kwargs) -> R:
    """Execute an extension skill command.
    
    Example: extension_skill("youtube", "play")
             extension_skill("youtube", "volume", level=50)
    """
    return _exec(f"skill:{skill_name}:{command_name}", kwargs, timeout=15)


# YouTube skill shortcuts (if youtube_skill.js is loaded)
def youtube_play():         return extension_skill("youtube", "play")
def youtube_pause():        return extension_skill("youtube", "pause")
def youtube_resume():       return extension_skill("youtube", "resume")
def youtube_mute():         return extension_skill("youtube", "mute")
def youtube_unmute():       return extension_skill("youtube", "unmute")
def youtube_volume(level:int): return extension_skill("youtube", "volume", level=level)
def youtube_speed(rate:float): return extension_skill("youtube", "speed", rate=rate)
def youtube_skip(seconds:int=10): return extension_skill("youtube", "skip", seconds=seconds)
def youtube_back(seconds:int=10): return extension_skill("youtube", "back", seconds=seconds)
def youtube_fullscreen():   return extension_skill("youtube", "fullscreen")
def youtube_info():         return extension_skill("youtube", "info")
def youtube_next():         return extension_skill("youtube", "next")
def youtube_like():         return extension_skill("youtube", "like")
def youtube_subscribe():    return extension_skill("youtube", "subscribe")
