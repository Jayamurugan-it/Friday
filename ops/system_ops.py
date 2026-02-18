"""
Friday System Operations — CMD Arm
All actual system ops: volume, wifi, bt, files, packages,
services, processes, clipboard, brightness, apps, network,
archives, venv, docker, ssh, cron, env, pomodoro, etc.
"""

import os
import re
import sys
import time
import shutil
import platform
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from db.database import (
    save_wifi, get_wifi, touch_wifi, list_wifi as _lw,
    save_bt, get_bt, list_bt as _lbt,
    log_install, log_uninstall, list_packages as _lp,
    save_clipboard, list_clipboard as _lcb,
)

OS = platform.system().lower()  # linux | darwin | windows


@dataclass
class R:  # OpResult
    ok:   bool
    out:  str
    cmd:  str = ""
    undo: Optional[str] = None


def _run(cmd, timeout=45, shell=True):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out or "(done)"
    except subprocess.TimeoutExpired:
        return False, f"[Timed out after {timeout}s]"
    except Exception as e:
        return False, f"[Error: {e}]"


def _sudo(cmd):
    if OS == "windows" or os.geteuid() == 0: return cmd
    return f"sudo {cmd}"


def _detect_manager():
    for m in ("pip","apt","brew","dnf","pacman","npm"):
        if shutil.which(m): return m
    return "pip"


# ════════════ VOLUME ════════════

def get_volume():
    if OS == "linux":   ok, o = _run("pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null || amixer get Master")
    elif OS == "darwin": ok, o = _run("osascript -e 'output volume of (get volume settings)'")
    else:               ok, o = _run('powershell -c "(Get-AudioDevice -Playback).Volume"')
    return R(ok, o, "get_volume")

def set_volume(level: int):
    level = max(0, min(100, level))
    if OS == "linux":   cmd = f"pactl set-sink-volume @DEFAULT_SINK@ {level}% 2>/dev/null || amixer -q set Master {level}%"
    elif OS == "darwin": cmd = f"osascript -e 'set volume output volume {level}'"
    else:               cmd = f'powershell -c "$obj=New-Object -com wscript.shell; for($i=0;$i -lt 50;$i++){{$obj.SendKeys([char]174)}}"'
    ok, o = _run(cmd)
    return R(ok, f"Volume → {level}%" if ok else o, cmd, undo="# restore previous volume")

def mute_volume(mute=True):
    if OS == "linux":   cmd = f"pactl set-sink-mute @DEFAULT_SINK@ {'1' if mute else '0'} 2>/dev/null || amixer -q set Master {'mute' if mute else 'unmute'}"
    elif OS == "darwin": cmd = f"osascript -e 'set volume {'with' if mute else 'without'} output muted'"
    else:               cmd = ""
    ok, o = _run(cmd) if cmd else (True, "")
    return R(ok, f"Audio {'muted' if mute else 'unmuted'}", cmd)


# ════════════ WIFI ════════════

def list_wifi_networks():
    if OS == "linux":   ok, o = _run("nmcli -f SSID,SECURITY,SIGNAL device wifi list 2>/dev/null")
    elif OS == "darwin": ok, o = _run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s")
    else:               ok, o = _run("netsh wlan show networks")
    return R(ok, o, "list_wifi")

def connect_wifi(ssid, password=None):
    stored = get_wifi(ssid)
    pwd = password or (stored["password"] if stored else None)
    if OS == "linux":
        cmd = f'nmcli device wifi connect "{ssid}" password "{pwd}"' if pwd else f'nmcli device wifi connect "{ssid}"'
    elif OS == "darwin":
        cmd = f'networksetup -setairportnetwork en0 "{ssid}" "{pwd}"' if pwd else f'networksetup -setairportnetwork en0 "{ssid}"'
    else:
        cmd = f'netsh wlan connect name="{ssid}"'
    ok, o = _run(cmd, timeout=25)
    if ok and pwd: save_wifi(ssid, pwd); touch_wifi(ssid)
    return R(ok, f"Connected to {ssid}" if ok else o, cmd, undo=f'nmcli connection down "{ssid}"')

def disconnect_wifi(ssid=None):
    if OS == "linux":   cmd = f'nmcli connection down "{ssid}"' if ssid else "nmcli networking off && nmcli networking on"
    elif OS == "darwin": cmd = "networksetup -setairportpower en0 off && sleep 1 && networksetup -setairportpower en0 on"
    else:               cmd = "netsh wlan disconnect"
    ok, o = _run(cmd, timeout=15)
    return R(ok, f"Disconnected" if ok else o, cmd)

def save_wifi_creds(ssid, password, security="WPA2"):
    save_wifi(ssid, password, security)
    return R(True, f"Saved WiFi '{ssid}' to database", "db")

def get_saved_wifi():
    nets = _lw()
    if not nets: return R(True, "No WiFi credentials stored", "db")
    lines = [f"  {n['ssid']:<28} [{n['security']}]  last:{(n['last_used'] or 'never')[:10]}" for n in nets]
    return R(True, "Saved WiFi:\n" + "\n".join(lines), "db")

def hotspot_create(ssid, password, band="bg"):
    if OS == "linux":
        cmd = f'nmcli device wifi hotspot ssid "{ssid}" password "{password}" band {band}'
    elif OS == "darwin":
        return R(False, "Use System Preferences → Sharing → Internet Sharing", "")
    else:
        cmd = f'netsh wlan set hostednetwork mode=allow ssid="{ssid}" key="{password}" && netsh wlan start hostednetwork'
    ok, o = _run(cmd, timeout=20)
    return R(ok, f"Hotspot '{ssid}' {'started' if ok else 'failed: '+o}", cmd)

def change_dns(primary, secondary="8.8.4.4"):
    if OS == "linux":
        content = f"nameserver {primary}\nnameserver {secondary}\n"
        try:
            Path("/etc/resolv.conf").write_text(content)
            return R(True, f"DNS → {primary}, {secondary}", "file_write", undo="# restore /etc/resolv.conf")
        except Exception as e:
            return R(False, str(e), "")
    elif OS == "darwin":
        cmd = f'networksetup -setdnsservers Wi-Fi {primary} {secondary}'
        ok, o = _run(cmd)
        return R(ok, f"DNS changed" if ok else o, cmd)
    return R(False, "Not supported on this OS", "")

def speed_test():
    ok, o = _run("speedtest-cli --simple 2>/dev/null || python3 -m speedtest --simple 2>/dev/null", timeout=60)
    return R(ok, o or "speedtest-cli not installed. Run: pip install speedtest-cli", "speedtest")

def network_scan():
    ok, o = _run("ip route | grep 'src' | awk '{print $1}' | head -1", timeout=5)
    subnet = o.strip() if ok else "192.168.1.0/24"
    ok2, o2 = _run(f"nmap -sn {subnet} 2>/dev/null || arp -a", timeout=30)
    return R(ok2, o2, f"nmap -sn {subnet}")

def net_info():
    if OS == "linux":   ok, o = _run("ip -s link && netstat -i 2>/dev/null || ss -s")
    elif OS == "darwin": ok, o = _run("netstat -ib")
    else:               ok, o = _run("netstat -e")
    return R(ok, o, "net_info")


# ════════════ BLUETOOTH ════════════

def scan_bluetooth():
    if OS == "linux":   ok, o = _run("bluetoothctl devices && bluetoothctl info", timeout=10)
    elif OS == "darwin": ok, o = _run("system_profiler SPBluetoothDataType | head -40")
    else:               ok, o = _run("Get-PnpDevice -Class Bluetooth | Select FriendlyName,Status")
    return R(ok, o, "bt_scan")

def connect_bluetooth(name_or_mac):
    device = get_bt(name_or_mac)
    mac = device["mac"] if device else name_or_mac
    if OS == "linux":   cmd = f"bluetoothctl connect {mac}"
    elif OS == "darwin": cmd = f"blueutil --connect {mac}"
    else: return R(False, "Use Windows BT settings", "")
    ok, o = _run(cmd, timeout=20)
    if ok and device: save_bt(device["name"], mac, device.get("dtype","unknown"), True)
    return R(ok, f"Connected to {device['name'] if device else mac}" if ok else o, cmd,
             undo=f"bluetoothctl disconnect {mac}")

def disconnect_bluetooth(name_or_mac):
    device = get_bt(name_or_mac)
    mac = device["mac"] if device else name_or_mac
    if OS == "linux":   cmd = f"bluetoothctl disconnect {mac}"
    elif OS == "darwin": cmd = f"blueutil --disconnect {mac}"
    else: return R(False, "Use Windows BT settings", "")
    ok, o = _run(cmd, timeout=15)
    return R(ok, f"Disconnected from {device['name'] if device else mac}" if ok else o, cmd)

def pair_bluetooth(mac, name=""):
    if OS == "linux":
        ok, o = _run(f"bluetoothctl pair {mac}", timeout=30)
        if ok: save_bt(name or mac, mac)
        return R(ok, f"Paired {name or mac}" if ok else o, f"bluetoothctl pair {mac}")
    return R(False, "Not supported", "")

def list_bt_devices():
    devs = _lbt()
    if not devs: return R(True, "No BT devices in database", "db")
    lines = [f"  {d['name']:<25} {(d['mac'] or 'N/A'):<20} [{d['dtype']}] {'✓' if d['trusted'] else ''}" for d in devs]
    return R(True, "Bluetooth devices:\n" + "\n".join(lines), "db")


# ════════════ FILES ════════════

def move_file(src, dst):
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    if not s.exists(): return R(False, f"Not found: {src}", "mv")
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(s), str(d))
    return R(True, f"Moved: {src} → {dst}", f"mv '{src}' '{dst}'", undo=f"mv '{dst}' '{src}'")

def copy_file(src, dst):
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    if not s.exists(): return R(False, f"Not found: {src}", "cp")
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(s), str(d)) if s.is_dir() else shutil.copy2(str(s), str(d))
    return R(True, f"Copied: {src} → {dst}", f"cp '{src}' '{dst}'", undo=f"rm -rf '{dst}'")

def delete_file(path):
    p = Path(path).expanduser()
    if not p.exists(): return R(False, f"Not found: {path}", "rm")
    trash = Path.home() / ".friday" / "trash"
    trash.mkdir(parents=True, exist_ok=True)
    dest = trash / p.name
    shutil.move(str(p), str(dest))
    return R(True, f"Moved to trash: {p.name}  (restore: mv '{dest}' '{p}')", f"trash: {dest}",
             undo=f"mv '{dest}' '{p}'")

def create_dir(path):
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return R(True, f"Created: {path}", f"mkdir -p '{path}'", undo=f"rmdir '{path}'")

def list_dir(path="."):
    p = Path(path).expanduser()
    if not p.exists(): return R(False, f"Not found: {path}", "ls")
    items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:60]
    lines = [f"  {'📄' if i.is_file() else '📁'}  {i.name:<40} {i.stat().st_size:>10,}" if i.is_file()
             else f"  📁  {i.name}/" for i in items]
    return R(True, f"{p.resolve()}/\n" + "\n".join(lines), f"ls '{path}'")

def read_file(path, max_chars=8000):
    p = Path(path).expanduser()
    if not p.exists(): return R(False, f"Not found: {path}", "cat")
    try:
        text = p.read_text(errors="replace")
        if len(text) > max_chars: text = text[:max_chars] + f"\n... [{len(text)} total chars, truncated]"
        return R(True, text, f"cat '{path}'")
    except Exception as e:
        return R(False, str(e), "")

def write_file(path, content, mode="write"):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w" if mode == "write" else "a") as f:
        f.write(content)
    return R(True, f"{'Wrote' if mode=='write' else 'Appended'} {len(content)} chars to {path}", f"write '{path}'")

def file_search(query, path="~", dtype=None, days=None):
    p = Path(path).expanduser()
    cmd = f'find "{p}" -name "*{query}*"'
    if dtype == "file":   cmd += " -type f"
    elif dtype == "dir":  cmd += " -type d"
    if days: cmd += f" -mtime -{days}"
    cmd += " 2>/dev/null | head -30"
    ok, o = _run(cmd, timeout=20)
    return R(ok, o or f"No results for '{query}'", cmd)

def bulk_rename(path, pattern, replacement):
    p = Path(path).expanduser()
    renamed = []
    for f in p.iterdir():
        if pattern in f.name:
            new_name = f.name.replace(pattern, replacement)
            f.rename(p / new_name)
            renamed.append(f"{f.name} → {new_name}")
    return R(True, "\n".join(renamed) if renamed else "No files matched", f"bulk_rename '{path}'")

def duplicate_finder(path="~"):
    ok, o = _run(f'find "{Path(path).expanduser()}" -type f -exec md5sum {{}} + 2>/dev/null | sort | uniq -D -w32 | head -40', timeout=30)
    return R(ok, o or "No duplicates found", "dup_find")

def large_file_finder(path="~", min_mb=100):
    ok, o = _run(f'find "{Path(path).expanduser()}" -type f -size +{min_mb}M -exec ls -lh {{}} + 2>/dev/null | head -20', timeout=20)
    return R(ok, o or f"No files larger than {min_mb}MB found", "large_find")

def archive_files(path, output, fmt="zip"):
    p = Path(path).expanduser()
    out = Path(output).expanduser()
    if fmt == "zip":
        import zipfile
        with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as z:
            if p.is_dir():
                for f in p.rglob("*"):
                    z.write(f, f.relative_to(p.parent))
            else:
                z.write(p, p.name)
    else:
        import tarfile
        mode = "w:gz" if fmt == "tar.gz" else "w:bz2" if fmt == "tar.bz2" else "w"
        with tarfile.open(str(out), mode) as t:
            t.add(str(p), arcname=p.name)
    return R(True, f"Archived → {output}", f"archive '{path}' → '{output}'", undo=f"rm '{output}'")

def extract_archive(path, dest="."):
    p = Path(path).expanduser()
    d = Path(dest).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    name = p.name.lower()
    if name.endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(str(p)) as z: z.extractall(str(d))
    elif any(name.endswith(e) for e in (".tar.gz",".tgz",".tar.bz2",".tar")):
        import tarfile
        with tarfile.open(str(p)) as t: t.extractall(str(d))
    else:
        return R(False, f"Unsupported archive format: {p.suffix}", "")
    return R(True, f"Extracted {path} → {dest}", f"extract '{path}'")


# ════════════ PACKAGES ════════════

def install_package(package, manager="auto"):
    if manager == "auto": manager = _detect_manager()
    cmds = {
        "pip":    f"pip install {package}",
        "apt":    _sudo(f"apt install -y {package}"),
        "brew":   f"brew install {package}",
        "dnf":    _sudo(f"dnf install -y {package}"),
        "pacman": _sudo(f"pacman -S --noconfirm {package}"),
        "npm":    f"npm install -g {package}",
        "snap":   _sudo(f"snap install {package}"),
    }
    cmd = cmds.get(manager, f"pip install {package}")
    ok, o = _run(cmd, timeout=180)
    if ok: log_install(package, manager)
    undo = {"pip":f"pip uninstall -y {package}","apt":_sudo(f"apt remove -y {package}"),"brew":f"brew uninstall {package}"}.get(manager)
    return R(ok, f"Installed {package} via {manager}" if ok else o, cmd, undo=undo)

def uninstall_package(package, manager="auto"):
    if manager == "auto": manager = _detect_manager()
    cmds = {"pip":f"pip uninstall -y {package}","apt":_sudo(f"apt remove -y {package}"),
            "brew":f"brew uninstall {package}","dnf":_sudo(f"dnf remove -y {package}"),
            "pacman":_sudo(f"pacman -R --noconfirm {package}"),"npm":f"npm uninstall -g {package}"}
    cmd = cmds.get(manager, f"pip uninstall -y {package}")
    ok, o = _run(cmd, timeout=120)
    if ok: log_uninstall(package, manager)
    return R(ok, f"Uninstalled {package}" if ok else o, cmd)


# ════════════ SYSTEM ════════════

def system_info():
    lines = [f"  OS: {platform.system()} {platform.release()}", f"  Machine: {platform.machine()}",
             f"  Python: {sys.version.split()[0]}", f"  Host: {platform.node()}"]
    try:
        import psutil
        m = psutil.virtual_memory(); d = psutil.disk_usage("/"); cpu = psutil.cpu_percent(0.3)
        lines += [f"  CPU: {cpu}% ({psutil.cpu_count()} cores)",
                  f"  RAM: {m.used>>20:,} / {m.total>>20:,} MB ({m.percent}%)",
                  f"  Disk: {d.used>>30:.1f} / {d.total>>30:.1f} GB ({d.percent}%)"]
    except ImportError:
        ok, o = _run("free -h && df -h /"); lines.append(o)
    return R(True, "\n".join(lines), "system_info")

def list_processes(filter_name=None):
    cmd = f"ps aux | grep -i '{filter_name}' | grep -v grep" if filter_name else "ps aux --sort=-%mem | head -20"
    ok, o = _run(cmd)
    return R(ok, o, cmd)

def kill_process(pid=None, name=None):
    if pid: cmd = f"kill -15 {pid}"
    elif name: cmd = f"pkill -15 -f '{name}'"
    else: return R(False, "Provide pid or name", "")
    ok, o = _run(cmd)
    return R(ok, f"Killed {pid or name}" if ok else o, cmd)

def disk_usage(path="/"):
    ok, o = _run(f"df -h '{path}'")
    return R(ok, o, f"df -h '{path}'")

def get_ip():
    if OS == "linux":   ok, o = _run("ip addr show | grep 'inet ' | awk '{print $2, $NF}'")
    elif OS == "darwin": ok, o = _run("ifconfig | grep 'inet ' | grep -v 127")
    else:               ok, o = _run("ipconfig")
    return R(ok, o, "get_ip")

def service_action(name, action):
    if OS == "linux":   cmd = _sudo(f"systemctl {action} {name}")
    elif OS == "darwin": cmd = f"brew services {action} {name}" if action in ("start","stop","restart") else f"launchctl {action} {name}"
    else:               cmd = f"sc {action} {name}"
    ok, o = _run(cmd, timeout=20)
    inv = {"start":"stop","stop":"start","enable":"disable","disable":"enable"}
    undo = _sudo(f"systemctl {inv[action]} {name}") if action in inv else None
    return R(ok, o or f"{name} {action}ed", cmd, undo=undo)

def launch_app(app_name):
    if OS == "linux":
        for cmd in [app_name, app_name.lower(), app_name.replace(" ","-").lower()]:
            if shutil.which(cmd):
                subprocess.Popen([cmd], start_new_session=True)
                return R(True, f"Launched {app_name}", cmd)
        return R(False, f"App '{app_name}' not found in PATH", "")
    elif OS == "darwin":
        ok, o = _run(f'open -a "{app_name}"')
        return R(ok, f"Launched {app_name}" if ok else o, f'open -a "{app_name}"')
    else:
        ok, o = _run(f'start "" "{app_name}"')
        return R(ok, f"Launched {app_name}" if ok else o, "")

def set_brightness(level: int):
    level = max(0, min(100, level))
    if OS == "linux":
        ok, o = _run(f"brightnessctl set {level}% 2>/dev/null || xrandr --output $(xrandr | grep ' connected' | head -1 | cut -d' ' -f1) --brightness {level/100:.2f}")
    elif OS == "darwin":
        ok, o = _run(f"osascript -e 'tell application \"System Events\" to set brightness of displays to {level/100:.2f}'")
    else:
        ok, o = False, "Not supported on Windows via CLI"
    return R(ok, f"Brightness → {level}%" if ok else o, f"brightness {level}")

def lock_screen():
    if OS == "linux":   cmd = "loginctl lock-session 2>/dev/null || xdg-screensaver lock 2>/dev/null || gnome-screensaver-command -l"
    elif OS == "darwin": cmd = "/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend"
    else:               cmd = "rundll32.exe user32.dll,LockWorkStation"
    ok, o = _run(cmd)
    return R(ok, "Screen locked" if ok else o, cmd)


# ════════════ CLIPBOARD ════════════

def get_clipboard():
    if OS == "linux":   ok, o = _run("xclip -selection clipboard -o 2>/dev/null || xsel --clipboard --output 2>/dev/null || wl-paste 2>/dev/null")
    elif OS == "darwin": ok, o = _run("pbpaste")
    else:               ok, o = _run("powershell -c Get-Clipboard")
    return R(ok, o, "get_clipboard")

def set_clipboard(text):
    if OS == "linux":   cmd = f"echo '{text}' | xclip -selection clipboard 2>/dev/null || echo '{text}' | xsel --clipboard --input 2>/dev/null || echo '{text}' | wl-copy 2>/dev/null"
    elif OS == "darwin": cmd = f"echo '{text}' | pbcopy"
    else:               cmd = f'powershell -c "Set-Clipboard \'{text}\'"'
    ok, o = _run(cmd)
    if ok: save_clipboard(text)
    return R(ok, f"Copied to clipboard: {text[:50]}", cmd)

def clipboard_history():
    items = _lcb(10)
    if not items: return R(True, "Clipboard history empty", "db")
    lines = [f"  [{i['ts'][11:16]}] {i['content'][:60]}" for i in items]
    return R(True, "Clipboard history:\n" + "\n".join(lines), "db")


# ════════════ VIRTUAL ENV ════════════

def create_venv(path, python="python3"):
    ok, o = _run(f"{python} -m venv '{Path(path).expanduser()}'", timeout=30)
    return R(ok, f"venv created at {path}" if ok else o, f"python -m venv '{path}'",
             undo=f"rm -rf '{path}'")

def list_venvs(search_path="~"):
    ok, o = _run(f'find "{Path(search_path).expanduser()}" -name "pyvenv.cfg" -maxdepth 5 2>/dev/null | head -20', timeout=15)
    if ok and o:
        lines = [str(Path(p).parent) for p in o.splitlines()]
        return R(True, "Python venvs:\n" + "\n".join(f"  {v}" for v in lines), "find_venv")
    return R(ok, "No venvs found", "find_venv")


# ════════════ DOCKER ════════════

def docker_ps(all_=False):
    cmd = "docker ps -a" if all_ else "docker ps"
    ok, o = _run(cmd, timeout=10)
    return R(ok, o, cmd)

def docker_action(container, action):
    cmd = f"docker {action} {container}"
    ok, o = _run(cmd, timeout=30)
    inv = {"start":"stop","stop":"start"}
    return R(ok, o or f"{container} {action}ed", cmd, undo=f"docker {inv.get(action,'start')} {container}" if action in inv else None)

def docker_logs(container, lines=50):
    ok, o = _run(f"docker logs --tail={lines} {container}", timeout=15)
    return R(ok, o, f"docker logs {container}")

def docker_images():
    ok, o = _run("docker images", timeout=10)
    return R(ok, o, "docker images")


# ════════════ SSH ════════════

def ssh_connect(host, user=None, port=22, key=None):
    user_prefix = f"{user}@" if user else ""
    key_opt = f"-i '{key}'" if key else ""
    cmd = f"ssh {key_opt} -p {port} {user_prefix}{host}"
    # Open in new terminal
    if OS == "linux":
        term = shutil.which("gnome-terminal") or shutil.which("xterm") or shutil.which("konsole")
        if term:
            subprocess.Popen([term, "--", "bash", "-c", f"{cmd}; read"])
            return R(True, f"SSH session opened: {user_prefix}{host}:{port}", cmd)
    ok, o = _run(cmd + " -o ConnectTimeout=10 'exit'", timeout=15)
    return R(ok, f"Connected to {host}" if ok else o, cmd)

def port_check(port, host="localhost"):
    ok, o = _run(f"ss -tlnp | grep ':{port}' 2>/dev/null || netstat -tlnp 2>/dev/null | grep ':{port}'", timeout=5)
    if not o.strip():
        return R(True, f"Nothing listening on port {port}", f"ss :{port}")
    return R(ok, o, f"ss :{port}")

def kill_port(port):
    ok, o = _run(f"fuser -k {port}/tcp 2>/dev/null || lsof -ti:{port} | xargs kill -9 2>/dev/null", timeout=10)
    return R(ok, f"Killed process on port {port}" if ok else o, f"kill :{port}")


# ════════════ CRON / SCHEDULER ════════════

def list_cron():
    ok, o = _run("crontab -l 2>/dev/null")
    return R(ok, o or "No cron jobs", "crontab -l")

def add_cron(schedule, command, name=""):
    ok, existing = _run("crontab -l 2>/dev/null")
    entry = f"# friday:{name}\n{schedule} {command}" if name else f"{schedule} {command}"
    new_cron = (existing.strip() + "\n" + entry).strip() + "\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cron", delete=False) as f:
        f.write(new_cron); tmp = f.name
    ok, o = _run(f"crontab {tmp}"); os.unlink(tmp)
    return R(ok, f"Cron added: {schedule} {command}" if ok else o, f"crontab", undo="crontab -r")

def remove_cron(pattern):
    ok, existing = _run("crontab -l 2>/dev/null")
    lines = [l for l in existing.splitlines() if pattern not in l]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cron", delete=False) as f:
        f.write("\n".join(lines) + "\n"); tmp = f.name
    ok, o = _run(f"crontab {tmp}"); os.unlink(tmp)
    return R(ok, f"Removed cron matching '{pattern}'" if ok else o, "crontab")


# ════════════ ENV FILE ════════════

def env_read(path=".env"):
    p = Path(path).expanduser()
    if not p.exists(): return R(False, f"Not found: {path}", "")
    lines = []
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key = line.split("=")[0]
            lines.append(f"  {key}=***")
        else:
            lines.append(f"  {line}")
    return R(True, f"{path}:\n" + "\n".join(lines), f"cat {path}")

def env_write(path, key, value):
    p = Path(path).expanduser()
    content = p.read_text() if p.exists() else ""
    lines = content.splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"; found = True; break
    if not found: lines.append(f"{key}={value}")
    p.write_text("\n".join(lines) + "\n")
    return R(True, f"Set {key} in {path}", f"env_write '{path}'")


# ════════════ POMODORO ════════════

_pomo_state = {"active": False, "start": None, "task": "", "session": 0}

def start_pomodoro(task="Focus", minutes=25):
    _pomo_state.update({"active": True, "start": time.time(), "task": task,
                        "duration": minutes * 60, "session": _pomo_state["session"] + 1})
    return R(True, f"🍅 Pomodoro #{_pomo_state['session']} started: {task} ({minutes}min)", "pomodoro")

def pomodoro_status():
    if not _pomo_state["active"]: return R(True, "No active Pomodoro", "pomodoro")
    elapsed = int(time.time() - _pomo_state["start"])
    remaining = max(0, _pomo_state["duration"] - elapsed)
    mins, secs = divmod(remaining, 60)
    return R(True, f"🍅 {_pomo_state['task']}: {mins:02d}:{secs:02d} remaining (session #{_pomo_state['session']})", "pomodoro")

def stop_pomodoro():
    _pomo_state["active"] = False
    return R(True, "Pomodoro stopped", "pomodoro")


# ════════════ RUN PYTHON ════════════

def run_python(code, timeout=15):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code); tmp = f.name
    try:
        ok, o = _run(f"python3 '{tmp}'", timeout=timeout)
        return R(ok, o, "python3")
    finally:
        os.unlink(tmp)


# ════════════ SAFE SHELL ════════════

SAFE_CMDS = {
    "ls","pwd","echo","cat","head","tail","grep","find","which","whoami","id",
    "uname","date","uptime","df","du","free","ps","env","printenv","hostname",
    "ping","curl","wget","dig","nslookup","traceroute","netstat","ss","ip",
    "ifconfig","lsblk","lspci","lsusb","dmesg","journalctl","git","docker",
    "systemctl","nmcli","bluetoothctl","amixer","pactl","pip","apt","brew",
}

def safe_shell(cmd):
    base = cmd.strip().split()[0].split("/")[-1]
    if base not in SAFE_CMDS:
        return R(False, f"'{base}' not in safe list. Use run_python for custom logic.", cmd)
    ok, o = _run(cmd, timeout=20)
    return R(ok, o, cmd)
