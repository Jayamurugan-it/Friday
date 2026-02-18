"""
Friday AI — Master Agent
Two arms: CMD (system) + Browser (Chrome extension)
Intent memory, multi-step planner, risk gating, habit learning.
"""
import os, json, time, platform
from groq import Groq
from core.risk import classify_tool, Risk
from memory.memory import infer_preferences, record_tool_choice, build_context

# ── System arm imports ─────────────────────────────────────────────────────────
from ops.system_ops import (
    get_volume, set_volume, mute_volume,
    list_wifi_networks, connect_wifi, disconnect_wifi, save_wifi_creds, get_saved_wifi,
    hotspot_create, change_dns, speed_test, network_scan, net_info,
    scan_bluetooth, connect_bluetooth, disconnect_bluetooth, pair_bluetooth, list_bt_devices,
    move_file, copy_file, delete_file, create_dir, list_dir, read_file, write_file,
    file_search, bulk_rename, duplicate_finder, large_file_finder, archive_files, extract_archive,
    install_package, uninstall_package,
    system_info, list_processes, kill_process, disk_usage, get_ip,
    service_action, launch_app, set_brightness, lock_screen,
    get_clipboard, set_clipboard, clipboard_history,
    create_venv, list_venvs,
    docker_ps, docker_action, docker_logs, docker_images,
    ssh_connect, port_check, kill_port,
    list_cron, add_cron, remove_cron,
    env_read, env_write,
    start_pomodoro, pomodoro_status, stop_pomodoro,
    run_python, safe_shell,
)

# ── Web tools ──────────────────────────────────────────────────────────────────
from tools.web_tools import (
    web_search, fetch_page, get_weather, get_datetime,
    calculate, get_stock, wikipedia, convert_currency, convert_units,
    generate_qr, api_test, start_local_server,
)

# ── Browser arm ────────────────────────────────────────────────────────────────
from tools.browser_tools import (
    navigate, go_back, go_forward, reload, get_url, get_title,
    click, fill_input, fill_form, select_option, check_box,
    scroll, hover, press_key, wait_for,
    get_text, get_html, read_page, extract_table, find_element, get_links, get_form_fields,
    get_tabs, open_tab, close_tab, focus_tab, close_other_tabs, find_tab, close_tabs_by_domain,
    get_cookies, get_storage, trigger_download, run_js, dom_op,
    auto_login, save_login, list_logins,
    start_recording, stop_recording, replay_session, list_sessions_info,
    save_form, fill_saved_form, ask_about_page,
    # Extension skills
    youtube_play, youtube_pause, youtube_resume, youtube_mute, youtube_unmute,
    youtube_volume, youtube_speed, youtube_skip, youtube_back, youtube_fullscreen,
    youtube_info, youtube_next, youtube_like, youtube_subscribe,
)

# ── Memory & DB tools ──────────────────────────────────────────────────────────
from memory.memory import (
    remember_fact, recall_facts, show_facts,
    save_note, show_notes, find_note,
    add_reminder_nlp, show_reminders, done_reminder,
    create_goal, progress_goal, complete_goal, show_goals,
    get_habits_summary,
)
from db.database import (
    log_cmd, get_history, get_undoable, mark_undone, db_stats,
    save_alias, get_alias, list_aliases, bump_alias,
    save_snippet, get_snippet, list_snippets,
    vault_save, vault_get, vault_list,
    get_pref, set_pref,
    add_watcher, remove_watcher, list_watchers,
)


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt(session_ctx=None):
    ctx = build_context()
    session_part = session_ctx.as_prompt_context() if session_ctx else ""
    return f"""You are Friday, a powerful AI system agent running on {platform.system()}.

You have TWO arms:
1. CMD ARM — control the local computer (files, processes, wifi, bluetooth, packages, docker, cron, etc.)
2. BROWSER ARM — control Chrome via extension (navigate, click, fill, extract, tab management, JS injection, auto-login, session replay)

PERSONALITY: Fast. Direct. No filler. No "Sure!" or "Of course!". Results only.

RULES:
- Pick the right tool immediately. Never guess — use tools.
- For browser ops: use browser_* tools. Extension must be active in Chrome.
- For WiFi/BT: stored credentials are used automatically.
- For packages: detect manager from habits or system.
- After tool results: reply in 1–3 sentences max.
- Multi-step tasks: plan silently, execute tools in sequence, report once at end.
- If page Q&A requested: read_page first, then answer from content.
- Intent memory: your tool choices teach Friday your preferences automatically.

NATURAL FOLLOW-UPS:
- User never needs to repeat context. "louder" after volume → increase volume.
- "increase to 100" after youtube volume → set youtube volume to 100.
- "pause" when on youtube → pause youtube. "resume" → play.
- "mute it", "turn it up", "a bit lower" → use active context.
- Short inputs like "50", "100", "louder", "mute" resolve from last action.
- Always prefer the active session context over asking for clarification.

ACTIVE SESSION:
{session_part if session_part else "(no recent actions)"}

MEMORY CONTEXT:
{ctx if ctx else "(no active reminders or goals)"}
"""


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

def _tf(name, desc, props, required=None):
    # Groq fails to call tools with empty props={} unless schema is explicit.
    # Adding additionalProperties:false fixes the failed_generation error.
    parameters = {
        "type": "object",
        "properties": props,
        "required": required or [],
        "additionalProperties": False,
    }
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": parameters}}

def _s(desc): return {"type":"string","description":desc}
def _i(desc): return {"type":"integer","description":desc}
def _b(desc): return {"type":"boolean","description":desc}
def _n(desc): return {"type":"number","description":desc}

TOOLS = [
    # ── VOLUME ──
    _tf("volume","Volume control — action: get|set|mute|unmute  level(0-100) required only for set",
        {"action":_s("get|set|mute|unmute"),"level":{"type":"integer","description":"0-100, only used when action is set"}},["action"]),

    # ── WIFI ──
    _tf("list_wifi_networks","Scan WiFi networks",{}),
    _tf("connect_wifi","Connect to WiFi",{"ssid":_s("network name"),"password":_s("optional if stored")},["ssid"]),
    _tf("disconnect_wifi","Disconnect WiFi",{"ssid":_s("network name")}),
    _tf("save_wifi_creds","Save WiFi password to DB",{"ssid":_s(""),"password":_s(""),"security":_s("WPA2")},["ssid","password"]),
    _tf("get_saved_wifi","List saved WiFi networks",{}),
    _tf("hotspot_create","Create WiFi hotspot",{"ssid":_s(""),"password":_s("")},["ssid","password"]),
    _tf("change_dns","Change DNS servers",{"primary":_s("e.g. 8.8.8.8")},["primary"]),
    _tf("speed_test","Run internet speed test",{}),
    _tf("network_scan","Scan local network for devices",{}),
    _tf("net_info","Network interface stats",{}),

    # ── BLUETOOTH ──
    _tf("bluetooth","Bluetooth — action: scan|connect|disconnect|pair|list  device: name or MAC",
        {"action":_s("scan|connect|disconnect|pair|list"),
         "device":_s("device name or MAC address"),"name":_s("friendly name for pair")},["action"]),

    # ── FILES ──
    _tf("move_file","Move file/dir",{"source":_s(""),"destination":_s("")},["source","destination"]),
    _tf("copy_file","Copy file/dir",{"source":_s(""),"destination":_s("")},["source","destination"]),
    _tf("delete_file","Delete file (to Friday trash)",{"path":_s("")},["path"]),
    _tf("create_dir","Create directory",{"path":_s("")},["path"]),
    _tf("list_dir","List directory",{"path":_s("default '.'")},),
    _tf("read_file","Read file contents",{"path":_s("")},["path"]),
    _tf("write_file","Write text to file",{"path":_s(""),"content":_s(""),"mode":_s("write or append")},["path","content"]),
    _tf("file_search","Search for files",{"query":_s("filename pattern"),"path":_s("search root"),"dtype":_s("file|dir"),"days":_i("modified within N days")}),
    _tf("bulk_rename","Rename files matching pattern",{"path":_s(""),"pattern":_s("text to find"),"replacement":_s("text to replace")},["path","pattern","replacement"]),
    _tf("file_finder","Find files — type: duplicates|large  path required  min_mb for large",
        {"type":_s("duplicates|large"),"path":_s("search root"),"min_mb":_i("min size MB for large")},["type","path"]),
    _tf("archive_files","Archive files to zip/tar",{"path":_s(""),"output":_s("output path"),"fmt":_s("zip|tar.gz|tar.bz2")},["path","output"]),
    _tf("extract_archive","Extract archive",{"path":_s(""),"dest":_s("destination dir")},["path"]),

    # ── PACKAGES ──
    _tf("install_package","Install package",{"package":_s(""),"manager":_s("pip|apt|brew|npm|auto")},["package"]),
    _tf("uninstall_package","Uninstall package",{"package":_s(""),"manager":_s("auto")},["package"]),

    # ── SYSTEM ──
    _tf("system_info","System info CPU/RAM/disk",{}),
    _tf("list_processes","List processes",{"filter_name":_s("optional filter")}),
    _tf("kill_process","Kill process",{"pid":_i("PID"),"name":_s("process name")}),
    _tf("disk_usage","Disk usage",{"path":_s("default /")}),
    _tf("get_ip","Get IP addresses",{}),
    _tf("get_location","Get current geographic location based on IP address — city, region, country, coordinates",{}),
    _tf("service_action","Control system service",{"name":_s(""),"action":_s("start|stop|restart|status|enable|disable")},["name","action"]),
    _tf("launch_app","Launch application",{"app_name":_s("application name")},["app_name"]),
    _tf("set_brightness","Set screen brightness 0-100",{"level":_i("0-100")},["level"]),
    _tf("lock_screen","Lock the screen",{}),

    # ── CLIPBOARD ──
    _tf("clipboard","Clipboard — action: get|set|history  text required for set",
        {"action":_s("get|set|history"),"text":_s("text to copy")},["action"]),

    # ── VENV / DOCKER / SSH ──
    _tf("venv","Python virtualenv — action: create|list  path for create  search_path for list",
        {"action":_s("create|list"),"path":_s("venv path"),
         "search_path":_s("search root, default ~")},["action"]),
    _tf("docker","Docker — action: ps|images|start|stop|restart|rm|logs  container for most actions  all_ to include stopped in ps",
        {"action":_s("ps|images|start|stop|restart|rm|logs"),"container":_s(""),"all_":_b("include stopped"),"lines":_i("log lines, default 50")},["action"]),
    _tf("ssh_connect","SSH to remote host",{"host":_s(""),"user":_s(""),"port":_i("default 22"),"key":_s("key path")},["host"]),
    _tf("port_check","Check what's on a port",{"port":_i("")},["port"]),
    _tf("kill_port","Kill process on port",{"port":_i("")},["port"]),

    # ── CRON ──
    _tf("cron","Cron jobs — action: list|add|remove  schedule+command for add  pattern for remove",
        {"action":_s("list|add|remove"),"schedule":_s("e.g. 0 8 * * *"),"command":_s(""),"name":_s("label"),"pattern":_s("for remove")},["action"]),

    # ── ENV ──
    _tf("env_read","Read .env file",{"path":_s("default .env")}),
    _tf("env_write","Set key in .env file",{"path":_s(""),"key":_s(""),"value":_s("")},["path","key","value"]),

    # ── POMODORO ──
    _tf("pomodoro","Pomodoro — action: start|status|stop  task+minutes for start",
        {"action":_s("start|status|stop"),"task":_s(""),"minutes":_i("default 25")},["action"]),

    # ── CODE ──
    _tf("run_python","Run Python code snippet",{"code":_s("")},["code"]),
    _tf("safe_shell","Run safe read-only shell command",{"cmd":_s("")},["cmd"]),

    # ── WEB TOOLS ──
    _tf("web_search","Search the web",{"query":_s("")},["query"]),
    _tf("fetch_page","Fetch and read a webpage",{"url":_s("")},["url"]),
    _tf("get_weather","Get weather forecast",{"location":_s("")},["location"]),
    _tf("get_datetime","Get current date/time",{"timezone":_s("e.g. America/New_York")}),
    _tf("calculate","Math calculation",{"expression":_s("e.g. sqrt(144)")},["expression"]),
    _tf("get_stock","Stock price",{"symbol":_s("ticker e.g. AAPL")},["symbol"]),
    _tf("wikipedia","Wikipedia summary",{"topic":_s("")},["topic"]),
    _tf("convert_currency","Currency conversion",{"amount":_n(""),"from_cur":_s(""),"to_cur":_s("")},["amount","from_cur","to_cur"]),
    _tf("convert_units","Unit conversion",{"value":_n(""),"from_unit":_s(""),"to_unit":_s("")},["value","from_unit","to_unit"]),
    _tf("generate_qr","Generate QR code",{"data":_s(""),"output_path":_s("optional file path")},["data"]),
    _tf("api_test","Test HTTP API endpoint",{"url":_s(""),"method":_s("GET|POST|PUT|DELETE"),"body":{"type":"object"}},["url"]),
    _tf("start_local_server","Start local HTTP server",{"port":_i("default 8080"),"directory":_s("default .")}),

    # ════════════ BROWSER ARM ════════════
    _tf("navigate","Navigate browser to URL",{"url":_s("")},["url"]),
    _tf("browser_nav","Browser navigation — action: back|forward|reload|get_url|get_title",
        {"action":_s("back|forward|reload|get_url|get_title")},["action"]),
    _tf("click","Click element on page",{"selector":_s("CSS selector"),"text":_s("button/link text"),"index":_i("if multiple matches")}),
    _tf("fill_input","Fill an input field",{"selector":_s("CSS selector"),"value":_s("value to fill")},["selector","value"]),
    _tf("fill_form","Fill multiple form fields",{"fields":{"type":"object","description":"selector→value map"}},["fields"]),
    _tf("select_option","Select dropdown option",{"selector":_s(""),"value":_s("option value"),"text":_s("option text")},["selector"]),
    _tf("check_box","Check/uncheck checkbox",{"selector":_s(""),"checked":_b("true=check")},["selector"]),
    _tf("scroll","Scroll page",{"direction":_s("up|down|left|right"),"amount":_i("pixels"),"selector":_s("element to scroll")}),
    _tf("hover","Hover over element",{"selector":_s("")},["selector"]),
    _tf("press_key","Press keyboard key",{"key":_s("e.g. Enter, Tab, Escape"),"selector":_s("optional focus target")},["key"]),
    _tf("wait_for","Wait for element to appear",{"selector":_s(""),"timeout_ms":_i("milliseconds")},["selector"]),
    _tf("read_page","Extract all readable text from current page",{}),
    _tf("page_extract","Extract specific content — type: text|html|table|links|form_fields  optional selector",
        {"type":_s("text|html|table|links|form_fields"),
         "selector":_s("optional CSS selector"),"index":_i("table index"),"outer":_b("include tag")},["type"]),
    _tf("find_element","Find element by description",{"description":_s("e.g. 'the submit button'")},["description"]),
    _tf("get_links","Get all links on page",{"selector":_s("optional container")}),
    _tf("get_form_fields","Get all form fields on page",{}),
    _tf("browser_tab","Tab management — action: list|open|close|focus|close_others|close_by_domain  url/index/domain as needed",
        {"action":_s("list|open|close|focus|close_others|close_by_domain"),
         "url":_s("for open"),"index":_i("for close/focus"),"domain":_s("for close_by_domain")},["action"]),
    _tf("find_tab","Find tab by title or URL",{"query":_s("")},["query"]),
    _tf("page_data","Get page data — type: cookies|local_storage|session_storage  optional domain",
        {"type":_s("cookies|local_storage|session_storage"),"domain":_s("optional")},["type"]),
    _tf("trigger_download","Download file from URL via browser",{"url":_s("")},["url"]),
    _tf("dom_op","Run a pre-defined browser operation — op: video_play|video_pause|video_toggle|video_mute|video_unmute|video_seek|video_speed|video_volume|video_info|scroll_down|scroll_up|scroll_top|scroll_bottom|page_title|page_url|page_text|click_el|focus_el|open_url|reload_page  value: optional param (seconds/rate/level/selector/url)",{"op":_s("operation name"),"value":_s("optional param")},["op"]),
    _tf("auto_login","Auto-login to site using stored credentials",{"site":_s("site name")},["site"]),
    _tf("login_manager","Manage saved logins — action: save|list  site+username+password for save",
        {"action":_s("save|list"),"site":_s(""),"username":_s(""),
         "password":_s(""),"url_pattern":_s("optional URL")},["action"]),
    _tf("browser_session","Browser session recording — action: start|stop|replay|list  name required for start/replay",
        {"action":_s("start|stop|replay|list"),"name":_s("session name")},["action"]),
    _tf("form_memory","Save or fill form values — action: save|fill  name required",
        {"action":_s("save|fill"),"name":_s("form name")},["action","name"]),
    _tf("ask_about_page","Answer a question about current page content",{"question":_s("")},["question"]),
    
    # ── EXTENSION SKILLS: YouTube ──
    _tf("youtube","Control YouTube video — action: play|pause|resume|mute|unmute|info|next|like|subscribe|fullscreen|set_volume|set_speed|skip|back  level for set_volume(0-100)  rate for set_speed(0.25-2.0)  seconds for skip/back",
        {"action":_s("play|pause|resume|mute|unmute|info|next|like|subscribe|fullscreen|set_volume|set_speed|skip|back"),
         "level":_i("volume 0-100, only for set_volume"),"rate":_n("speed 0.25-2.0, only for set_speed"),"seconds":_i("skip/back seconds")},["action"]),

    # ════════════ MEMORY & PRODUCTIVITY ════════════
    _tf("remember_fact","Save a fact to memory",{"content":_s(""),"category":_s("general|work|personal"),"importance":_n("0-2")},["content"]),
    _tf("recall_facts","Search facts in memory",{"query":_s("")},["query"]),
    _tf("show_facts","Show all stored facts",{"category":_s("optional filter")}),
    _tf("save_note","Save a note",{"title":_s(""),"content":_s(""),"tags":{"type":"array","items":{"type":"string"}}},["title","content"]),
    _tf("show_notes","List all notes",{}),
    _tf("find_note","Search notes",{"query":_s("")},["query"]),
    _tf("add_reminder_nlp","Set reminder with natural language time",{"text":_s(""),"when_str":_s("e.g. 'in 2 hours', 'tomorrow 9am'"),"repeat":_s("none|daily|weekly"),"priority":_s("low|normal|high")},["text","when_str"]),
    _tf("show_reminders","Show pending reminders",{}),
    _tf("done_reminder","Mark reminder as done",{"rid":_i("reminder ID")},["rid"]),
    _tf("create_goal","Create a goal",{"title":_s(""),"description":_s("")},["title"]),
    _tf("progress_goal","Update goal progress",{"gid":_i("goal ID"),"progress":_i("0-100")},["gid","progress"]),
    _tf("complete_goal","Mark goal as complete",{"gid":_i("goal ID")},["gid"]),
    _tf("show_goals","Show goals",{"status":_s("active|completed")}),
    _tf("get_habits_summary","Show all learned habits and preferences",{}),

    # ── ALIASES ──
    _tf("alias","Manage command aliases — action: save|run|list  name+command for save  name for run",
        {"action":_s("save|run|list"),"name":_s("alias name"),
         "command":_s("command for save"),"description":_s("")},["action"]),

    # ── SNIPPETS ──
    _tf("snippet","Code snippets — action: save|get|list  name+content for save  name for get",
        {"action":_s("save|get|list"),"name":_s("snippet name"),
         "content":_s("code content"),"language":_s("language")},["action"]),

    # ── VAULT ──
    _tf("vault","Password vault — action: save|get|list  label+username+password for save  label for get",
        {"action":_s("save|get|list"),"label":_s("entry name"),
         "username":_s(""),"password":_s(""),"url":_s("")},["action"]),

    # ── WATCHERS ──
    _tf("watcher","Process watcher — action: add|remove|list  process name for add/remove",
        {"action":_s("add|remove|list"),"process":_s("process name"),
         "auto_restart":_b("restart if it dies"),"alert":_b("alert on change")},["action"]),

    # ── SKILLS ──
    _tf("skill_help","Skill system help — type: template|extension_template|open_folder",
        {"type":_s("template|extension_template|open_folder")},["type"]),
    _tf("skills_cmd","Skills management — action: list|reload|status",
        {"action":_s("list|reload|status")},["action"]),
    _tf("diagnose_skill_cmd","Show detailed validation report for one skill",
        {"skill_name":_s("Skill name to diagnose")},["skill_name"]),
    _tf("validate_js_skill_cmd","Validate a JS extension skill file",
        {"path":_s("Path to .js skill file")},["path"]),

    # ── META ──
    _tf("show_history","Show recent command history",{"limit":_i("default 15"),"arm":_s("cmd|browser")}),
    _tf("db_stats","Database statistics",{}),
    _tf("undo_last","Undo last recoverable operation",{}),
    _tf("set_pref","Save a preference",{"key":_s(""),"value":_s("")},["key","value"]),
]


# ══════════════════════════════════════════════════════════════════════════════
# GROUPED TOOL DISPATCH FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _youtube_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    dispatch = {
        "play":        youtube_play,
        "pause":       youtube_pause,
        "resume":      youtube_resume,
        "mute":        youtube_mute,
        "unmute":      youtube_unmute,
        "fullscreen":  youtube_fullscreen,
        "info":        youtube_info,
        "next":        youtube_next,
        "like":        youtube_like,
        "subscribe":   youtube_subscribe,
    }
    if act in dispatch:
        return dispatch[act]()
    if act in ("volume", "set_volume"):
        return youtube_volume(int(a.get("level", 50)))
    if act in ("speed", "set_speed"):
        return youtube_speed(float(a.get("rate", 1.0)))
    if act in ("skip", "forward"):
        return youtube_skip(int(a.get("seconds", 10)))
    if act in ("back", "rewind"):
        return youtube_back(int(a.get("seconds", 10)))
    return R(False, f"Unknown youtube action: {act}. Use: play|pause|resume|mute|unmute|volume|speed|skip|back|fullscreen|info|next|like|subscribe", "youtube")


def _bluetooth_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    dev = a.get("device","")
    if act == "scan":        return scan_bluetooth()
    if act == "connect":     return connect_bluetooth(dev)
    if act == "disconnect":  return disconnect_bluetooth(dev)
    if act == "pair":        return pair_bluetooth(dev, a.get("name", dev))
    if act == "list":        return list_bt_devices()
    return R(False, f"Unknown bluetooth action: {act}. Use: scan|connect|disconnect|pair|list", "bluetooth")


def _browser_tab_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    if act == "list":           return get_tabs()
    if act == "open":           return open_tab(a.get("url","about:blank"))
    if act == "close":          return close_tab(a.get("index"))
    if act == "focus":          return focus_tab(a["index"])
    if act == "close_others":   return close_other_tabs()
    if act == "close_by_domain":return close_tabs_by_domain(a["domain"])
    return R(False, f"Unknown browser_tab action: {act}. Use: list|open|close|focus|close_others|close_by_domain", "browser_tab")


def _browser_session_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    if act == "start":   return start_recording(a.get("name", f"session_{int(__import__('time').time())}"))
    if act == "stop":    return stop_recording()
    if act == "replay":  return replay_session(a["name"])
    if act == "list":    return list_sessions_info()
    return R(False, f"Unknown browser_session action: {act}. Use: start|stop|replay|list", "browser_session")


def _alias_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    if act == "save":
        save_alias(a["name"], a["command"], a.get("description",""))
        return R(True, f"Alias '{a['name']}' saved → {a['command']}", "db")
    if act == "run":
        return _run_alias(a)
    if act == "list":
        rows = list_aliases()
        body = "\n".join(f"  {r['name']:<20} {r['command'][:60]}" for r in rows) if rows else "No aliases saved"
        return R(True, "Aliases:\n" + body, "db")
    return R(False, f"Unknown alias action: {act}. Use: save|run|list", "alias")


def _snippet_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    if act == "save":
        save_snippet(a["name"], a["content"], a.get("language","text"))
        return R(True, f"Snippet '{a['name']}' saved", "db")
    if act == "get":
        s = get_snippet(a["name"])
        return R(bool(s), s["content"] if s else f"Snippet '{a['name']}' not found", "db")
    if act == "list":
        rows = list_snippets()
        body = "\n".join(f"  {r['name']:<20} [{r['language']}]" for r in rows) if rows else "No snippets"
        return R(True, "Snippets:\n" + body, "db")
    return R(False, f"Unknown snippet action: {act}. Use: save|get|list", "snippet")


def _vault_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    if act == "save":
        vault_save(a["label"], a["username"], a["password"], a.get("url",""), a.get("notes",""))
        return R(True, f"Vault: '{a['label']}' saved", "db")
    if act == "get":
        v = vault_get(a["label"])
        return R(bool(v), f"🔐 {v['label']}: {v['username']} / {v['password']}" if v else f"Not found: {a['label']}", "db")
    if act == "list":
        rows = vault_list()
        body = "\n".join(f"  {r['label']:<20} {r['username']}" for r in rows) if rows else "Vault is empty"
        return R(True, "Vault:\n" + body, "db")
    return R(False, f"Unknown vault action: {act}. Use: save|get|list", "vault")


def _watcher_dispatch(a):
    from ops.system_ops import R
    act = a.get("action","").lower()
    if act == "add":
        add_watcher(a["process"], a.get("auto_restart", False), a.get("alert", True))
        return R(True, f"Watching: {a['process']}", "db")
    if act == "remove":
        remove_watcher(a["process"])
        return R(True, f"Stopped watching: {a['process']}", "db")
    if act == "list":
        rows = list_watchers()
        body = "\n".join(f"  {r['process']} (restart={r['auto_restart']})" for r in rows) if rows else "No active watchers"
        return R(True, "Watchers:\n" + body, "db")
    return R(False, f"Unknown watcher action: {act}. Use: add|remove|list", "watcher")


def _skill_help_dispatch(a):
    t = a.get("type","").lower()
    if t == "template":           return _skill_template(a)
    if t == "extension_template": return _extension_skill_template(a)
    if t == "open_folder":        return _open_skill_folder(a)
    from ops.system_ops import R
    return R(False, "Unknown type. Use: template|extension_template|open_folder", "skill_help")


def _page_extract_dispatch(a):
    t = a.get("type","").lower()
    if t == "text":        return get_text(a.get("selector"))
    if t == "html":        return get_html(a.get("selector"), a.get("outer", False))
    if t == "table":       return extract_table(a.get("selector"), a.get("index", 0))
    if t == "links":       return get_links(a.get("selector"))
    if t == "form_fields": return get_form_fields()
    from ops.system_ops import R
    return R(False, f"Unknown extract type: {t}. Use: text|html|table|links|form_fields", "page_extract")


# ══════════════════════════════════════════════════════════════════════════════
# SKILL MANAGEMENT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _skill_template(a):
    """Show skill template - opens file or displays in terminal."""
    from pathlib import Path
    import platform
    from ops.system_ops import R
    
    template_path = Path(__file__).parent.parent / "SKILL_TEMPLATE.md"
    
    if not template_path.exists():
        return R(False, "SKILL_TEMPLATE.md not found", "skill_template")
    
    # Try to open in default editor
    OS = platform.system().lower()
    try:
        if OS == "linux":
            import subprocess
            subprocess.Popen(["xdg-open", str(template_path)])
        elif OS == "darwin":
            import subprocess
            subprocess.Popen(["open", str(template_path)])
        elif OS == "windows":
            import os
            os.startfile(str(template_path))
        return R(True, f"Opened skill template: {template_path}", "skill_template")
    except:
        # Fallback: show first 50 lines
        content = template_path.read_text()
        lines = content.split("\n")[:50]
        preview = "\n".join(lines) + f"\n\n... [{len(content)} chars total]\n\nFull template: {template_path}"
        return R(True, preview, "skill_template")


def _extension_skill_template(a):
    """Show extension skill template for browser automation."""
    from pathlib import Path
    import platform
    from ops.system_ops import R
    
    template_path = Path(__file__).parent.parent / "EXTENSION_SKILL_TEMPLATE.md"
    
    if not template_path.exists():
        return R(False, "EXTENSION_SKILL_TEMPLATE.md not found", "extension_skill_template")
    
    # Try to open in default editor
    OS = platform.system().lower()
    try:
        if OS == "linux":
            import subprocess
            subprocess.Popen(["xdg-open", str(template_path)])
        elif OS == "darwin":
            import subprocess
            subprocess.Popen(["open", str(template_path)])
        elif OS == "windows":
            import os
            os.startfile(str(template_path))
        return R(True, f"Opened extension skill template: {template_path}", "extension_skill_template")
    except:
        # Fallback: show first 50 lines
        content = template_path.read_text()
        lines = content.split("\n")[:50]
        preview = "\n".join(lines) + f"\n\n... [{len(content)} chars total]\n\nFull template: {template_path}"
        return R(True, preview, "extension_skill_template")


def _extension_skill_template(a):
    """Show extension skill template - for browser automation skills."""
    from pathlib import Path
    import platform
    from ops.system_ops import R
    
    template_path = Path(__file__).parent.parent / "EXTENSION_SKILL_TEMPLATE.md"
    
    if not template_path.exists():
        return R(False, "EXTENSION_SKILL_TEMPLATE.md not found", "extension_skill_template")
    
    # Try to open in default editor
    OS = platform.system().lower()
    try:
        if OS == "linux":
            import subprocess
            subprocess.Popen(["xdg-open", str(template_path)])
        elif OS == "darwin":
            import subprocess
            subprocess.Popen(["open", str(template_path)])
        elif OS == "windows":
            import os
            os.startfile(str(template_path))
        return R(True, f"Opened extension skill template: {template_path}", "extension_skill_template")
    except:
        # Fallback: show first 50 lines
        content = template_path.read_text()
        lines = content.split("\n")[:50]
        preview = "\n".join(lines) + f"\n\n... [{len(content)} chars total]\n\nFull template: {template_path}"
        return R(True, preview, "extension_skill_template")


def _open_skill_folder(a):
    """Open skills folder in file manager."""
    from pathlib import Path
    import platform
    import subprocess
    from ops.system_ops import R
    
    skills_dir = Path(__file__).parent.parent / "skills"
    OS = platform.system().lower()
    
    try:
        if OS == "linux":
            subprocess.Popen(["xdg-open", str(skills_dir)])
        elif OS == "darwin":
            subprocess.Popen(["open", str(skills_dir)])
        elif OS == "windows":
            import os
            os.startfile(str(skills_dir))
        return R(True, f"Opened skills folder: {skills_dir}", "open_skill_folder")
    except Exception as e:
        return R(False, f"Could not open folder: {e}\nPath: {skills_dir}", "open_skill_folder")


def _list_skills(a):
    """List all loaded skills."""
    from skills.registry import list_loaded_skills, get_tool_defs
    from ops.system_ops import R

    skills = list_loaded_skills()
    if not skills:
        return R(True, "No custom skills loaded. Add .py files to skills/ folder.", "list_skills")

    # Count tools per skill
    all_tool_defs = get_tool_defs()
    tool_counts = {}
    for skill_name in skills:
        count = sum(1 for t in all_tool_defs if skill_name in str(t.get("function", {}).get("name", "")))
        tool_counts[skill_name] = count

    lines = [f"Loaded skills ({len(skills)}):\n"]
    for skill in skills:
        count = tool_counts.get(skill, 0)
        lines.append(f"  📦 {skill:<25} {count} tools")

    lines.append(f"\nTotal tools from skills: {len(all_tool_defs)}")
    lines.append(f"\nTo add skills: drop .py files in skills/ folder")
    lines.append(f"Template: say 'skill template'")

    return R(True, "\n".join(lines), "list_skills")


def _reload_skills_cmd(a):
    """Reload all skills - validates each one before loading."""
    from skills.registry import reload_skills, all_skills_summary
    from ops.system_ops import R
    skill_tools, skill_handlers = reload_skills()
    summary = all_skills_summary()
    return R(True, f"Reload complete.\n\n{summary}", "reload_skills")


def _skill_status_cmd(a):
    """Show full validation status for all loaded skills."""
    from skills.registry import all_skills_summary, list_failed_skills
    from ops.system_ops import R
    summary = all_skills_summary()
    failed  = list_failed_skills()
    if failed:
        summary += f"\n\nTo diagnose a failed skill: 'diagnose skill {failed[0]}'"
    return R(True, summary, "skill_status")


def _diagnose_skill_cmd(a):
    """Show detailed validation report for one skill."""
    from skills.registry import skill_report, get_skill_status
    from ops.system_ops import R
    name   = a.get("skill_name", "").strip()
    report = skill_report(name)
    status = get_skill_status(name)

    if not status:
        return R(False,
                 f"Skill '{name}' not found.\n"
                 f"Available: {', '.join(__import__('skills.registry', fromlist=['list_loaded_skills']).list_loaded_skills())}",
                 "diagnose_skill")

    extra = ""
    if not status["ok"]:
        extra = (
            "\n\nHow to fix:\n"
            "1. Open the skill file in your editor\n"
            "2. Fix the errors listed above\n"
            "3. Save the file\n"
            "4. Friday auto-detects and retries in 2 seconds\n"
            "5. Say 'skill status' to check again"
        )
    return R(status["ok"], report + extra, "diagnose_skill")


def _validate_js_skill_cmd(a):
    """Validate a JS extension skill file before installing it."""
    from pathlib import Path
    from skills.registry import validate_js_skill_file
    from ops.system_ops import R
    path = Path(a.get("path", "")).expanduser()
    if not path.exists():
        return R(False, f"File not found: {path}", "validate_js")
    if not path.suffix == ".js":
        return R(False, f"Expected a .js file, got: {path.suffix}", "validate_js")
    report = validate_js_skill_file(path)
    return R(True, report, "validate_js")


# ══════════════════════════════════════════════════════════════════════════════
# LOCATION HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _get_location():
    """Get geographic location from IP using ipinfo.io (no API key required)."""
    from ops.system_ops import R
    try:
        import urllib.request, json
        with urllib.request.urlopen("https://ipinfo.io/json", timeout=6) as resp:
            data = json.loads(resp.read())
        city    = data.get("city", "?")
        region  = data.get("region", "?")
        country = data.get("country", "?")
        loc     = data.get("loc", "?,?")
        org     = data.get("org", "")
        out = f"Location: {city}, {region}, {country}\nCoordinates: {loc}\nISP/Org: {org}"
        return R(True, out, "ipinfo.io")
    except Exception as e:
        return R(False, f"Could not determine location: {e}", "ipinfo.io")


# ══════════════════════════════════════════════════════════════════════════════
# TOOL MAP
# ══════════════════════════════════════════════════════════════════════════════

def _make_map():
    def wr(fn, *keys):
        def _call(a): return fn(*[a[k] for k in keys])
        return _call
    def wro(fn, **defaults):
        def _call(a):
            kwargs = {k: a.get(k, v) for k, v in defaults.items()}
            return fn(**kwargs)
        return _call

    from ops.system_ops import R as OpR

    def _history(a):
        from ops.system_ops import R
        rows = get_history(a.get("limit",15), a.get("arm"))
        if not rows: return R(True,"No history","db")
        lines = [f"  {'✓' if r['success'] else '✗'} [{r['ts'][11:16]}] [{r['arm']}] {r['user_input'][:50]}" for r in rows]
        return R(True,"\n".join(lines),"db")

    def _undo(a):
        from ops.system_ops import _run, R
        u = get_undoable()
        if not u: return R(False,"Nothing to undo","")
        last = u[0]
        ok, out = _run(last["undo_cmd"])
        if ok: mark_undone(last["id"])
        return R(ok, f"Undone: {last['user_input']}\n{out}" if ok else f"Undo failed: {out}", last["undo_cmd"])

    def _run_alias(a):
        from ops.system_ops import _run, R
        alias = get_alias(a["name"])
        if not alias: return R(False, f"Alias '{a['name']}' not found","db")
        bump_alias(a["name"])
        ok, out = _run(alias["command"])
        return R(ok, out, alias["command"])

    def _ask_page(a):
        from ops.system_ops import R
        result = ask_about_page(a["question"])
        if not result.ok: return result
        if "PAGE_CONTENT_FOR_QA::" in result.out:
            _, rest = result.out.split("PAGE_CONTENT_FOR_QA::", 1)
            content, question = rest.split("::QUESTION::", 1)
            return R(True, f"[PAGE Q&A — content extracted, agent will answer]\nQuestion: {question}\nContent: {content[:3000]}", "page_qa")
        return result

    def _dstats(a):
        from ops.system_ops import R
        s = db_stats()
        lines = [f"  {k:<25} {v}" for k,v in s.items()]
        return R(True, "Friday DB:\n" + "\n".join(lines), "db")

    return {
        # Volume
        "volume": lambda a: get_volume() if a["action"]=="get" else (set_volume(int(a["level"])) if a["action"]=="set" else mute_volume(a["action"]=="mute")),
        # WiFi
        "list_wifi_networks": lambda a: list_wifi_networks(),
        "connect_wifi": lambda a: connect_wifi(a["ssid"], a.get("password")),
        "disconnect_wifi": lambda a: disconnect_wifi(a.get("ssid")),
        "save_wifi_creds": lambda a: save_wifi_creds(a["ssid"], a["password"], a.get("security","WPA2")),
        "get_saved_wifi": lambda a: get_saved_wifi(),
        "hotspot_create": lambda a: hotspot_create(a["ssid"], a["password"], a.get("band","bg")),
        "change_dns": lambda a: change_dns(a["primary"], a.get("secondary","8.8.4.4")),
        "speed_test": lambda a: speed_test(),
        "network_scan": lambda a: network_scan(),
        "net_info": lambda a: net_info(),
        # BT
        "bluetooth": _bluetooth_dispatch,
        # Files
        "move_file": lambda a: move_file(a["source"], a["destination"]),
        "copy_file": lambda a: copy_file(a["source"], a["destination"]),
        "delete_file": lambda a: delete_file(a["path"]),
        "create_dir": lambda a: create_dir(a["path"]),
        "list_dir": lambda a: list_dir(a.get("path",".")),
        "read_file": lambda a: read_file(a["path"]),
        "write_file": lambda a: write_file(a["path"], a["content"], a.get("mode","write")),
        "file_search": lambda a: file_search(a["query"], a.get("path","~"), a.get("dtype"), a.get("days")),
        "bulk_rename": lambda a: bulk_rename(a["path"], a["pattern"], a["replacement"]),
        "file_finder": lambda a: duplicate_finder(a.get("path","~")) if a["type"]=="duplicates" else large_file_finder(a.get("path","~"), a.get("min_mb",100)),
        "archive_files": lambda a: archive_files(a["path"], a["output"], a.get("fmt","zip")),
        "extract_archive": lambda a: extract_archive(a["path"], a.get("dest",".")),
        # Packages
        "install_package": lambda a: install_package(a["package"], a.get("manager","auto")),
        "uninstall_package": lambda a: uninstall_package(a["package"], a.get("manager","auto")),
        # System
        "system_info": lambda a: system_info(),
        "list_processes": lambda a: list_processes(a.get("filter_name")),
        "kill_process": lambda a: kill_process(a.get("pid"), a.get("name")),
        "disk_usage": lambda a: disk_usage(a.get("path","/")),
        "get_ip": lambda a: get_ip(),
        "get_location": lambda a: _get_location(),
        "service_action": lambda a: service_action(a["name"], a["action"]),
        "launch_app": lambda a: launch_app(a["app_name"]),
        "set_brightness": lambda a: set_brightness(a["level"]),
        "lock_screen": lambda a: lock_screen(),
        # Clipboard
        "clipboard": lambda a: get_clipboard() if a["action"]=="get" else (set_clipboard(a["text"]) if a["action"]=="set" else clipboard_history()),
        # Venv/Docker/SSH
        "venv": lambda a: create_venv(a["path"]) if a["action"]=="create" else list_venvs(a.get("search_path","~")),
        "docker": lambda a: docker_ps(a.get("all_",False)) if a["action"]=="ps" else (docker_images() if a["action"]=="images" else (docker_logs(a["container"], a.get("lines",50)) if a["action"]=="logs" else docker_action(a["container"], a["action"]))),
        "ssh_connect": lambda a: ssh_connect(a["host"], a.get("user"), a.get("port",22), a.get("key")),
        "port_check": lambda a: port_check(a["port"]),
        "kill_port": lambda a: kill_port(a["port"]),
        # Cron
        "cron": lambda a: list_cron() if a["action"]=="list" else (add_cron(a["schedule"], a["command"], a.get("name","")) if a["action"]=="add" else remove_cron(a["pattern"])),
        # Env
        "env_read": lambda a: env_read(a.get("path",".env")),
        "env_write": lambda a: env_write(a["path"], a["key"], a["value"]),
        # Pomodoro
        "pomodoro": lambda a: start_pomodoro(a.get("task","Focus"), a.get("minutes",25)) if a["action"]=="start" else (pomodoro_status() if a["action"]=="status" else stop_pomodoro()),
        # Code
        "run_python": lambda a: run_python(a["code"]),
        "safe_shell": lambda a: safe_shell(a["cmd"]),
        # Web
        "web_search": lambda a: web_search(a["query"]),
        "fetch_page": lambda a: fetch_page(a["url"]),
        "get_weather": lambda a: get_weather(a["location"]),
        "get_datetime": lambda a: get_datetime(a.get("timezone")),
        "calculate": lambda a: calculate(a["expression"]),
        "get_stock": lambda a: get_stock(a["symbol"]),
        "wikipedia": lambda a: wikipedia(a["topic"]),
        "convert_currency": lambda a: convert_currency(a["amount"], a["from_cur"], a["to_cur"]),
        "convert_units": lambda a: convert_units(a["value"], a["from_unit"], a["to_unit"]),
        "generate_qr": lambda a: generate_qr(a["data"], a.get("output_path")),
        "api_test": lambda a: api_test(a["url"], a.get("method","GET"), a.get("headers"), a.get("body")),
        "start_local_server": lambda a: start_local_server(a.get("port",8080), a.get("directory",".")),
        # Browser
        "navigate": lambda a: navigate(a["url"]),
        "browser_nav": lambda a: (go_back() if a["action"]=="back" else (go_forward() if a["action"]=="forward" else (reload() if a["action"]=="reload" else (get_url() if a["action"]=="get_url" else get_title())))),
        "click": lambda a: click(a.get("selector"), a.get("text"), a.get("index",0)),
        "fill_input": lambda a: fill_input(a["selector"], a["value"], a.get("clear_first",True)),
        "fill_form": lambda a: fill_form(a["fields"]),
        "select_option": lambda a: select_option(a["selector"], a.get("value"), a.get("text")),
        "check_box": lambda a: check_box(a["selector"], a.get("checked",True)),
        "scroll": lambda a: scroll(a.get("direction","down"), a.get("amount",500), a.get("selector")),
        "hover": lambda a: hover(a["selector"]),
        "press_key": lambda a: press_key(a["key"], a.get("selector")),
        "wait_for": lambda a: wait_for(a["selector"], a.get("timeout_ms",5000)),
        "read_page": lambda a: read_page(),
        "page_extract": _page_extract_dispatch,
        "find_element": lambda a: find_element(a["description"]),
        "browser_tab": _browser_tab_dispatch,
        "find_tab": lambda a: find_tab(a["query"]),
        "page_data": lambda a: get_cookies(a.get("domain")) if a["type"]=="cookies" else get_storage("local" if a["type"]=="local_storage" else "session"),
        "trigger_download": lambda a: trigger_download(a["url"]),
        "dom_op": lambda a: dom_op(a["op"], a.get("value", "")),
        "auto_login": lambda a: auto_login(a["site"]),
        "login_manager": lambda a: save_login(a["site"],a["username"],a["password"],a.get("url_pattern","")) if a["action"]=="save" else list_logins(),
        "browser_session": _browser_session_dispatch,
        "form_memory": lambda a: save_form(a["name"]) if a["action"]=="save" else fill_saved_form(a["name"]),
        "ask_about_page": _ask_page,
        # YouTube skills
        "youtube": _youtube_dispatch,
        # Memory
        "remember_fact": lambda a: remember_fact(a["content"], a.get("category","general"), a.get("importance",1.0)),
        "recall_facts": lambda a: recall_facts(a["query"]),
        "show_facts": lambda a: show_facts(a.get("category")),
        "save_note": lambda a: save_note(a["title"], a["content"], a.get("tags",[])),
        "show_notes": lambda a: show_notes(),
        "find_note": lambda a: find_note(a["query"]),
        "add_reminder_nlp": lambda a: add_reminder_nlp(a["text"], a["when_str"], a.get("repeat","none"), a.get("priority","normal")),
        "show_reminders": lambda a: show_reminders(),
        "done_reminder": lambda a: done_reminder(a["rid"]),
        "create_goal": lambda a: create_goal(a["title"], a.get("description","")),
        "progress_goal": lambda a: progress_goal(a["gid"], a["progress"]),
        "complete_goal": lambda a: complete_goal(a["gid"]),
        "show_goals": lambda a: show_goals(a.get("status","active")),
        "get_habits_summary": lambda a: (lambda h: __import__('ops.system_ops', fromlist=['R']).R(True, h, "db"))(get_habits_summary()),
        # Aliases
        "alias": _alias_dispatch,
        # Snippets
        "snippet": _snippet_dispatch,
        # Vault
        "vault": _vault_dispatch,
        # Watchers
        "watcher": _watcher_dispatch,
        # Skills
        "skill_help": _skill_help_dispatch,
        "skills_cmd": lambda a: _list_skills(a) if a["action"]=="list" else (_reload_skills_cmd(a) if a["action"]=="reload" else _skill_status_cmd(a)),
        "diagnose_skill_cmd":        _diagnose_skill_cmd,
        "validate_js_skill_cmd":     _validate_js_skill_cmd,
        # Meta
        "show_history": _history,
        "db_stats": _dstats,
        "undo_last": _undo,
        "set_pref": lambda a: (set_pref(a["key"], a["value"]), __import__('ops.system_ops', fromlist=['R']).R(True, f"Set {a['key']} = {a['value']}", "db"))[1],
    }

TOOL_MAP = _make_map()


# ══════════════════════════════════════════════════════════════════════════════
# AGENT CLASS
# ══════════════════════════════════════════════════════════════════════════════

class FridayAgent:
    def __init__(self, confirm_callback, output_callback,
                 extra_tools=None, extra_handlers=None):
        self.client   = Groq(api_key=os.getenv("GROQ_API_KEY",""))
        self.model    = os.getenv("MODEL","meta-llama/llama-4-scout-17b-16e-instruct")
        self.confirm  = confirm_callback
        self.out      = output_callback
        self.history  = []
        # Session context tracker — powers natural follow-up commands
        from core.context import SessionContext
        self.ctx = SessionContext()
        # Merge skill tools/handlers
        self._base_tools    = TOOLS
        self._base_handlers = TOOL_MAP
        self._skill_tools   = extra_tools or []
        self._skill_handlers = extra_handlers or {}
        self._rebuild_tools()

    def _rebuild_tools(self):
        """Rebuild tool list after skill reload."""
        combined = self._base_tools + self._skill_tools

        # Deduplicate by tool name (keep first occurrence)
        seen = set()
        deduped = []
        for t in combined:
            name = t.get("function", {}).get("name", "")
            if name and name not in seen:
                seen.add(name)
                deduped.append(t)

        # Groq (and most LLM APIs) cap tools at 128
        MAX_TOOLS = int(os.getenv("MAX_TOOLS", 128))
        if len(deduped) > MAX_TOOLS:
            import logging
            logging.getLogger("friday.agent").warning(
                f"Tool count {len(deduped)} exceeds MAX_TOOLS={MAX_TOOLS}. "
                f"Truncating to first {MAX_TOOLS} tools. "
                f"Set MAX_TOOLS env var or reduce loaded skills."
            )
            deduped = deduped[:MAX_TOOLS]

        self._tools    = deduped
        self._tool_map = {**self._base_handlers, **self._skill_handlers}

    def reload_skills(self):
        """Reload skills and rebuild tool list."""
        from skills.registry import reload_skills
        skill_tools, skill_handlers = reload_skills()
        self._skill_tools = skill_tools
        self._skill_handlers = skill_handlers
        self._rebuild_tools()
        return len(skill_tools)

    def _llm(self, messages):
        import groq as _groq
        try:
            return self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=self._tools, tool_choice="auto",
                max_tokens=int(os.getenv("MAX_TOKENS",4096)),
                temperature=float(os.getenv("TEMPERATURE",0.1)),
            )
        except _groq.BadRequestError as e:
            err = str(e)
            # tool_use_failed: model generated bad/empty tool call — retry without tools
            if "tool_use_failed" in err or "failed_generation" in err:
                import logging
                logging.getLogger("friday.agent").warning(
                    f"Model tool generation failed — retrying as plain chat. Detail: {err[:120]}"
                )
                return self.client.chat.completions.create(
                    model=self.model, messages=messages,
                    max_tokens=int(os.getenv("MAX_TOKENS",4096)),
                    temperature=float(os.getenv("TEMPERATURE",0.1)),
                )
            raise

    def _dispatch(self, name, args, user_input):
        t0 = time.time()
        risk = classify_tool(name, args)

        if risk.level == Risk.DANGEROUS:
            msg = risk.warn_msg or f"{name}({args})"
            if not self.confirm(msg, risk.level):
                log_cmd(user_input, name, str(args), risk.level, False, "Cancelled", None, 0, self._arm(name))
                return "⛔ Cancelled."

        # Augment args with learned preferences
        args = infer_preferences(user_input, name, args)

        fn = self._tool_map.get(name)
        if not fn:
            return f"[Unknown tool: {name}]"

        result = fn(args)
        ms = (time.time() - t0) * 1000

        # Learn from the choice
        record_tool_choice(name, args)

        out = getattr(result, "out", str(result))
        ok  = getattr(result, "ok",  True)

        # ── Update session context ─────────────────────────────────────────
        self.ctx.update(name, args, out, ok)

        # Log
        undo = getattr(result, "undo", None)
        log_cmd(user_input, name, getattr(result,"cmd",""), risk.level, ok,
                out, undo, ms, self._arm(name))

        if risk.level == Risk.RECOVERABLE and undo and ok:
            return out + "\n  ↩ undoable"
        return out

    def _arm(self, tool_name):
        browser_tools = {
            "navigate","browser_nav",
            "click","fill_input","fill_form","select_option","check_box","scroll",
            "hover","press_key","wait_for","get_text","get_html","read_page",
            "extract_table","find_element","get_links","get_form_fields",
            "get_tabs","open_tab","close_tab","focus_tab","close_other_tabs",
            "find_tab","close_tabs_by_domain","get_cookies","get_storage",
            "trigger_download","dom_op","auto_login","save_login","list_logins",
            "start_recording","stop_recording","replay_session","list_sessions_info",
            "save_form","fill_saved_form","ask_about_page",
        }
        return "browser" if tool_name in browser_tools else "cmd"

    def chat(self, user_input: str) -> str:
        raw_input = user_input.strip()

        # ── Fast-path: shorthand resolution for follow-ups ─────────────────
        # e.g. "louder", "100", "mute it", "pause" resolved locally
        shorthand = self.ctx.resolve_shorthand(raw_input)
        if shorthand:
            tool = shorthand["tool"]
            args = shorthand["args"]
            arm_icon = "🌐" if self._arm(tool) == "browser" else "⚙"
            self.out(f"  {arm_icon}  {tool}({args})", "tool")
            result = self._dispatch(tool, args, raw_input)
            reply = result or "Done."
            self.history.append({"role": "user",      "content": raw_input})
            self.history.append({"role": "assistant",  "content": reply})
            return reply

        # ── Full LLM path with session context injected ────────────────────
        self.history.append({"role": "user", "content": raw_input})
        messages = [{"role": "system", "content": _build_system_prompt(self.ctx)}]
        messages.extend(self.history[-14:])

        for _ in range(10):  # max iterations
            resp = self._llm(messages)
            choice = resp.choices[0]

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                tc_list = choice.message.tool_calls
                messages.append({
                    "role":"assistant","content":None,
                    "tool_calls":[{"id":tc.id,"type":"function",
                                   "function":{"name":tc.function.name,"arguments":tc.function.arguments}}
                                  for tc in tc_list]
                })
                for tc in tc_list:
                    name = tc.function.name
                    try: args = json.loads(tc.function.arguments)
                    except Exception: args = {}
                    arm = self._arm(name)
                    arm_icon = "🌐" if arm == "browser" else "⚙"
                    self.out(f"  {arm_icon}  {name}({', '.join(f'{k}={repr(v)[:30]}' for k,v in args.items())})", "tool")
                    result_text = self._dispatch(name, args, raw_input)
                    messages.append({"role":"tool","tool_call_id":tc.id,"content":result_text})
                continue

            final = choice.message.content or ""
            self.history.append({"role": "assistant", "content": final})
            return final

        return "Max iterations reached."
