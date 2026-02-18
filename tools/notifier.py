"""
Friday Notifier — desktop notifications + anomaly watcher
"""
import os, time, threading
from dataclasses import dataclass
from typing import Optional

@dataclass
class R:
    ok: bool; out: str


def _notify(title, message, urgency="normal"):
    """Send desktop notification cross-platform."""
    import platform
    OS = platform.system().lower()
    try:
        if OS == "linux":
            import subprocess
            icons = {"normal": "dialog-information", "critical": "dialog-warning", "low": "dialog-information"}
            subprocess.Popen(["notify-send", "-u", urgency, "-i", icons.get(urgency,"dialog-information"), title, message])
            return True
        elif OS == "darwin":
            import subprocess
            subprocess.Popen(["osascript", "-e", f'display notification "{message}" with title "{title}"'])
            return True
        else:
            try:
                from plyer import notification
                notification.notify(title=title, message=message, timeout=8)
                return True
            except ImportError:
                pass
    except Exception:
        pass
    return False


def notify(title, message, urgency="normal"):
    ok = _notify(title, message, urgency)
    return R(ok, f"Notified: {title} — {message}" if ok else "Notification failed (check plyer/notify-send)")


def alert(message):
    return notify("⚡ Friday", message, urgency="critical")


# ── Anomaly watcher ────────────────────────────────────────────────────────────

class AnomalyWatcher(threading.Thread):
    def __init__(self, cpu_thresh=90, ram_thresh=90, disk_thresh=90, interval=30):
        super().__init__(daemon=True)
        self.cpu_thresh  = cpu_thresh
        self.ram_thresh  = ram_thresh
        self.disk_thresh = disk_thresh
        self.interval    = interval
        self._stop       = threading.Event()

    def run(self):
        while not self._stop.wait(self.interval):
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent
                if cpu > self.cpu_thresh:
                    _notify("⚠ Friday Alert", f"CPU at {cpu:.0f}%!", "critical")
                if mem > self.ram_thresh:
                    _notify("⚠ Friday Alert", f"RAM at {mem:.0f}%!", "critical")
                if disk > self.disk_thresh:
                    _notify("⚠ Friday Alert", f"Disk at {disk:.0f}%!", "critical")
            except ImportError:
                break  # psutil not installed, stop watching
            except Exception:
                pass

    def stop(self):
        self._stop.set()


# ── Process watcher ────────────────────────────────────────────────────────────

class ProcessWatcher(threading.Thread):
    def __init__(self, interval=30):
        super().__init__(daemon=True)
        self.interval = interval
        self._stop    = threading.Event()

    def run(self):
        import subprocess
        from db.database import list_watchers, add_watcher
        while not self._stop.wait(self.interval):
            try:
                watchers = list_watchers()
                for w in watchers:
                    proc = w["process"]
                    result = subprocess.run(["pgrep", "-f", proc], capture_output=True)
                    running = result.returncode == 0
                    if not running:
                        if w.get("alert"):
                            _notify("⚠ Friday", f"Process '{proc}' is DOWN!", "critical")
                        if w.get("auto_restart"):
                            subprocess.Popen(proc.split(), start_new_session=True)
                            _notify("Friday", f"Auto-restarted: {proc}", "normal")
            except Exception:
                pass

    def stop(self):
        self._stop.set()
