"""
Friday Scheduler — proactive features
Morning digest, reminder polling, escalation, anomaly alerts.
"""
import threading, time, schedule
from datetime import datetime
from tools.notifier import notify, alert
from db.database import get_due_reminders, complete_reminder, escalate_reminder, list_goals, get_pref


class FridayScheduler(threading.Thread):
    def __init__(self, agent_callback=None):
        super().__init__(daemon=True)
        self.agent_callback = agent_callback  # fn(text) → send proactive message to REPL
        self._stop = threading.Event()

    def run(self):
        morning_time = get_pref("morning_briefing_time", "08:00")
        evening_time = get_pref("evening_summary_time", "21:00")

        schedule.every().day.at(morning_time).do(self._morning_briefing)
        schedule.every().day.at(evening_time).do(self._evening_summary)
        schedule.every(60).seconds.do(self._check_reminders)

        while not self._stop.wait(1):
            schedule.run_pending()

    def _morning_briefing(self):
        lines = ["☀️  Good morning! Here's your Friday briefing:\n"]
        try:
            from tools.web_tools import get_weather, get_datetime
            loc = get_pref("location","New York")
            wx = get_weather(loc); lines.append(wx.out[:300])
        except Exception: pass
        try:
            from db.database import get_pending_reminders
            reminders = get_pending_reminders()
            if reminders:
                lines.append(f"\n⏰ {len(reminders)} reminder(s) pending:")
                for r in reminders[:3]:
                    lines.append(f"  · {r['text']} (due {r['due_time'][11:16]})")
        except Exception: pass
        try:
            goals = list_goals("active")
            if goals:
                lines.append(f"\n🎯 {len(goals)} active goal(s):")
                for g in goals[:3]:
                    lines.append(f"  · {g['title']} — {g['progress']}%")
        except Exception: pass
        msg = "\n".join(lines)
        notify("⚡ Friday Morning Briefing", "Your daily summary is ready")
        if self.agent_callback: self.agent_callback(msg)

    def _evening_summary(self):
        try:
            from db.database import get_history
            today = datetime.now().strftime("%Y-%m-%d")
            history = [h for h in get_history(50) if h["ts"].startswith(today)]
            msg = f"🌙 Evening Summary — {len(history)} commands today"
            notify("⚡ Friday Evening", msg)
            if self.agent_callback: self.agent_callback(msg)
        except Exception: pass

    def _check_reminders(self):
        due = get_due_reminders()
        for r in due:
            text = r["text"]
            urgency = "critical" if r["priority"] == "high" else "normal"
            notify(f"⏰ Reminder {'⚠' if r['escalated'] else ''}", text, urgency)
            if r["escalated"]:
                alert(f"ESCALATED REMINDER: {text}")
            else:
                escalate_reminder(r["id"])
            if self.agent_callback:
                self.agent_callback(f"⏰ Reminder due: {text}")

    def stop(self):
        self._stop.set()
        schedule.clear()
