"""
Friday Risk Engine — CMD + Browser operations
SAFE → run instantly
RECOVERABLE → run + log undo
DANGEROUS → require y/n
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Risk(str, Enum):
    SAFE        = "SAFE"
    RECOVERABLE = "RECOVERABLE"
    DANGEROUS   = "DANGEROUS"


@dataclass
class RiskResult:
    level:    Risk
    reason:   str
    undo_cmd: Optional[str] = None
    warn_msg: Optional[str] = None


# ── CMD dangerous patterns ─────────────────────────────────────────────────────

_DANGER_CMD = [
    ("rm -rf",         "Recursive force delete — irreversible"),
    ("rm -r",          "Recursive delete — irreversible"),
    ("mkfs",           "Formats filesystem — destroys all data"),
    ("dd if=",         "Raw disk write — can destroy data"),
    ("fdisk",          "Disk partition change"),
    (":(){:|:&};:",    "Fork bomb — crashes system"),
    ("chmod -R 777 /", "Root permission change"),
    ("> /dev/sd",      "Direct disk write"),
    ("shred",          "Secure delete — irreversible"),
    ("wipefs",         "Wipes filesystem signatures"),
    ("shutdown",       "Shuts down system"),
    ("reboot",         "Reboots system"),
    ("halt",           "Halts system"),
    ("kill -9",        "Force kills process"),
    ("killall",        "Kills all matching processes"),
    ("iptables -F",    "Flushes all firewall rules"),
    ("passwd",         "Changes system password"),
    ("userdel",        "Deletes user account"),
    ("crontab -r",     "Removes all cron jobs"),
    ("DROP TABLE",     "Drops database table"),
    ("DROP DATABASE",  "Drops entire database"),
    ("TRUNCATE",       "Removes all table data"),
    ("format c:",      "Formats Windows drive"),
]

_SAFE_STARTS = [
    "ls","pwd","echo","cat ","head ","tail ","grep ","find ","which ",
    "whoami","id ","uname","date","uptime","df ","du ","free ","ps ",
    "env","printenv","hostname","ping -c","curl -I","dig ","nslookup",
    "netstat","ss ","ip addr","ifconfig","lsblk","lspci","lsusb",
    "systemctl status","nmcli device","nmcli con show","bluetoothctl list",
    "bluetoothctl info","amixer get","pactl list","pactl get",
    "pip list","pip show","apt list","brew list","git status","git log",
    "docker ps","docker images","journalctl","dmesg","lscpu",
]

_RECOVERABLE_CONTAINS = [
    "mv ","cp ","pip install","pip uninstall","apt install","apt remove",
    "brew install","brew uninstall","npm install","npm uninstall",
    "dnf install","dnf remove","pacman -S","pacman -R","snap install",
    "amixer set","pactl set","bluetoothctl connect","bluetoothctl disconnect",
    "nmcli connection","systemctl start","systemctl stop",
    "systemctl enable","systemctl disable","mkdir ","touch ","ln -s",
    "chmod ","chown ","docker start","docker stop","docker run",
]

# ── Browser dangerous ops ──────────────────────────────────────────────────────

_DANGER_BROWSER = {
    "delete_cookies":    "Deletes all cookies — you'll be logged out everywhere",
    "clear_storage":     "Clears all localStorage/sessionStorage",
    "submit_payment":    "Submits a payment form",
    "execute_arbitrary": "Runs arbitrary JavaScript on the page",
}

_SAFE_BROWSER = {
    "navigate", "scroll", "get_text", "get_html", "screenshot",
    "get_tabs", "get_url", "get_title", "get_cookies", "read_page",
    "extract_table", "find_element", "get_storage",
}

_RECOVERABLE_BROWSER = {
    "click", "fill_input", "select_option", "check_box", "fill_form",
    "close_tab", "open_tab", "focus_tab", "auto_login", "replay_session",
    "trigger_download", "fill_saved_form",
}


def classify_cmd(cmd: str) -> RiskResult:
    cmd_lower = cmd.lower().strip()

    for pattern, reason in _DANGER_CMD:
        if pattern.lower() in cmd_lower:
            return RiskResult(Risk.DANGEROUS, reason,
                              warn_msg=f"⚠ IRREVERSIBLE: {reason}")

    for s in _SAFE_STARTS:
        if cmd_lower.startswith(s.lower()):
            return RiskResult(Risk.SAFE, "Read-only operation")

    for s in _RECOVERABLE_CONTAINS:
        if s.lower() in cmd_lower:
            undo = _undo_for_cmd(cmd)
            return RiskResult(Risk.RECOVERABLE, "Reversible operation", undo_cmd=undo)

    return RiskResult(Risk.RECOVERABLE, "Unknown — logged for safety")


def classify_tool(tool: str, args: dict) -> RiskResult:
    if tool in _SAFE_BROWSER:
        return RiskResult(Risk.SAFE, "Read-only browser operation")
    if tool in _DANGER_BROWSER:
        return RiskResult(Risk.DANGEROUS, _DANGER_BROWSER[tool],
                          warn_msg=f"⚠ {_DANGER_BROWSER[tool]}")
    if tool in _RECOVERABLE_BROWSER:
        undo = _undo_for_tool(tool, args)
        return RiskResult(Risk.RECOVERABLE, "Reversible browser operation", undo_cmd=undo)

    # System tools
    _safe_sys = {"get_volume","list_wifi_networks","get_saved_wifi","list_bt_devices",
                 "system_info","list_processes","disk_usage","get_ip","list_packages",
                 "safe_shell","show_history","db_stats","get_clipboard","read_file",
                 "list_dir","file_search","net_info","speed_test","env_read",
                 "list_aliases","list_habits","list_reminders","list_goals","list_notes",
                 "list_facts","list_snippets","vault_list","list_credentials","list_sessions",
                 "list_watchers","get_time","pomodoro_status","list_cron"}
    _rec_sys = {"set_volume","mute_volume","connect_wifi","disconnect_wifi","save_wifi_creds",
                "connect_bluetooth","disconnect_bluetooth","pair_bluetooth",
                "move_file","copy_file","create_dir","install_package","uninstall_package",
                "kill_process","service_action","set_brightness","lock_screen","launch_app",
                "set_clipboard","write_file","create_alias","run_alias","add_reminder",
                "add_goal","add_fact","add_note","save_snippet","vault_save","save_credential",
                "add_watcher","remove_watcher","add_cron","remove_cron","run_python",
                "archive_files","extract_archive","bulk_rename","env_write",
                "start_pomodoro","stop_pomodoro","start_timer","network_scan"}
    _danger_sys = {"force_delete", "format_disk", "shutdown_system", "reboot_system"}

    # delete_file is RECOVERABLE for normal paths, DANGEROUS only for system paths
    if tool == "delete_file":
        path = str(args.get("path", ""))
        danger_paths = {"/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/boot", "/sys", "/proc"}
        is_danger = any(path == d or path.startswith(d + "/") for d in danger_paths)
        if is_danger:
            return RiskResult(Risk.DANGEROUS, f"System path deletion: {path}",
                              warn_msg=f"⚠ Deleting system path: {path}")
        return RiskResult(Risk.RECOVERABLE, "Moved to trash", undo_cmd=f"# restore from trash: {path}")

    if tool in _safe_sys:   return RiskResult(Risk.SAFE, "Read-only")
    if tool in _rec_sys:    return RiskResult(Risk.RECOVERABLE, "Reversible", undo_cmd=_undo_for_tool(tool, args))
    if tool in _danger_sys: return RiskResult(Risk.DANGEROUS, f"Irreversible: {tool}",
                                              warn_msg=f"⚠ This will {tool.replace('_',' ')} — irreversible")

    return RiskResult(Risk.RECOVERABLE, "Unknown tool — logged")


def _undo_for_cmd(cmd: str) -> Optional[str]:
    parts = cmd.strip().split()
    if not parts: return None
    base = parts[0].lower()
    if base == "mv" and len(parts) == 3:
        return f"mv '{parts[2]}' '{parts[1]}'"
    if base == "mkdir":
        return f"rmdir '{parts[-1]}'"
    if "pip" in base and "install" in cmd:
        pkgs = [p for p in parts[2:] if not p.startswith("-")]
        return f"pip uninstall -y {' '.join(pkgs)}" if pkgs else None
    if "apt" in cmd and "install" in cmd:
        pkgs = [p for p in parts if p not in ("apt","apt-get","install") and not p.startswith("-")]
        return f"sudo apt remove -y {' '.join(pkgs)}" if pkgs else None
    if "brew" in cmd and "install" in cmd:
        pkgs = [p for p in parts if p not in ("brew","install") and not p.startswith("-")]
        return f"brew uninstall {' '.join(pkgs)}" if pkgs else None
    return None


def _undo_for_tool(tool: str, args: dict) -> Optional[str]:
    if tool == "move_file":      return f"mv '{args.get('destination','')}' '{args.get('source','')}'"
    if tool == "create_dir":     return f"rmdir '{args.get('path','')}'"
    if tool == "install_package":
        m, p = args.get("manager","pip"), args.get("package","")
        return {"pip":f"pip uninstall -y {p}","apt":f"sudo apt remove -y {p}","brew":f"brew uninstall {p}"}.get(m)
    if tool == "service_action":
        inv = {"start":"stop","stop":"start","enable":"disable","disable":"enable"}
        return f"systemctl {inv.get(args.get('action',''),'status')} {args.get('name','')}"
    if tool == "connect_wifi":   return f"nmcli connection down \"{args.get('ssid','')}\""
    if tool == "close_tab":      return "# Cannot reopen closed tab automatically"
    return None
