"""
Friday Built-in Skill: InfoTools
Tools: battery_status, ping_host, public_ip, top_cpu_processes, top_ram_processes
"""
import subprocess
import platform
from dataclasses import dataclass

@dataclass
class R:
    ok: bool; out: str; cmd: str = ""


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


OS = platform.system().lower()


def battery_status():
    if OS == "linux":
        ok, o = _run("upower -i $(upower -e | grep BAT) 2>/dev/null | grep -E 'state|percentage|time'")
        if not ok or not o:
            ok, o = _run("cat /sys/class/power_supply/BAT*/capacity 2>/dev/null")
    elif OS == "darwin":
        ok, o = _run("pmset -g batt")
    else:
        cmd = 'powershell -c "Get-WmiObject Win32_Battery | Select-Object EstimatedChargeRemaining,BatteryStatus"'
        ok, o = _run(cmd)
    return R(ok, o or "No battery info available", "battery")


def ping_host(host: str, count: int = 4):
    flag = "-n" if OS == "windows" else "-c"
    ok, o = _run(f"ping {flag} {count} {host}", timeout=15)
    return R(ok, o, f"ping {host}")


def public_ip():
    try:
        import urllib.request, json
        with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as r:
            ip = json.loads(r.read()).get("ip", "?")
        return R(True, f"Public IP: {ip}", "public_ip")
    except Exception as e:
        return R(False, str(e), "public_ip")


def top_cpu_processes(n: int = 10):
    if OS == "windows":
        cmd = f'powershell -c "Get-Process | Sort-Object CPU -Descending | Select-Object -First {n} Name,CPU,WorkingSet | Format-Table -Auto"'
        ok, o = _run(cmd)
    else:
        ok, o = _run(f"ps aux --sort=-%cpu | head -{n+1}")
    return R(ok, o, "ps cpu")


def top_ram_processes(n: int = 10):
    if OS == "windows":
        cmd = f'powershell -c "Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First {n} Name,CPU,WorkingSet | Format-Table -Auto"'
        ok, o = _run(cmd)
    else:
        ok, o = _run(f"ps aux --sort=-%mem | head -{n+1}")
    return R(ok, o, "ps mem")


# ── Skill registration ─────────────────────────────────────────────────────────

def _tf(name, desc, props=None, required=None):
    return {"type":"function","function":{"name":name,"description":desc,
            "parameters":{"type":"object","properties":props or {},"required":required or [],
                           "additionalProperties":False}}}

def _s(d): return {"type":"string","description":d}
def _i(d): return {"type":"integer","description":d}


SKILL_TOOLS = [
    _tf("battery_status",    "Get battery level and charging status"),
    _tf("ping_host",         "Ping a host to check connectivity",
        {"host":_s("hostname or IP address"), "count":_i("number of packets, default 4")}, ["host"]),
    _tf("public_ip",         "Get the machine's public IP address"),
    _tf("top_cpu_processes", "Show top CPU-consuming processes", {"n":_i("number to show, default 10")}),
    _tf("top_ram_processes", "Show top RAM-consuming processes", {"n":_i("number to show, default 10")}),
]

SKILL_HANDLERS = {
    "battery_status":      lambda a: battery_status(),
    "ping_host":           lambda a: ping_host(a["host"], a.get("count", 4)),
    "public_ip":           lambda a: public_ip(),
    "top_cpu_processes":   lambda a: top_cpu_processes(a.get("n", 10)),
    "top_ram_processes":   lambda a: top_ram_processes(a.get("n", 10)),
}
