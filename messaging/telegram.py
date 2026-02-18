"""
Friday Telegram Bot — optional two-way control
Start with TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in .env
"""
import os
import threading
import time
import logging
from typing import Optional

log = logging.getLogger("friday.telegram")


class TelegramBot(threading.Thread):
    def __init__(self, agent_chat_fn):
        super().__init__(daemon=True)
        self.token   = os.getenv("TELEGRAM_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.agent   = agent_chat_fn   # fn(text) → str
        self._stop   = threading.Event()
        self._offset = 0
        self.enabled = bool(self.token and self.chat_id)

    def _get(self, method, params=None):
        try:
            import requests
            r = requests.get(
                f"https://api.telegram.org/bot{self.token}/{method}",
                params=params or {}, timeout=10
            )
            return r.json() if r.ok else {}
        except Exception:
            return {}

    def _send(self, text: str, parse_mode="Markdown"):
        try:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text[:4096], "parse_mode": parse_mode},
                timeout=10
            )
        except Exception as e:
            log.warning(f"Telegram send failed: {e}")

    def send(self, text: str):
        """Public method — call from anywhere to push a message."""
        if self.enabled:
            threading.Thread(target=self._send, args=(text,), daemon=True).start()

    def run(self):
        if not self.enabled:
            return

        self._send("⚡ *Friday AI online.* Send me anything.")
        log.info("Telegram bot started")

        while not self._stop.wait(1):
            try:
                updates = self._get("getUpdates", {"offset": self._offset, "timeout": 5})
                for upd in updates.get("result", []):
                    self._offset = upd["update_id"] + 1
                    msg = upd.get("message", {})
                    text = msg.get("text", "").strip()
                    sender = str(msg.get("chat", {}).get("id", ""))

                    # Only respond to authorized chat
                    if sender != self.chat_id:
                        continue

                    if not text:
                        continue

                    # Built-ins
                    if text.lower() in ("/start", "/help"):
                        self._send("⚡ *Friday AI* — send any command.\n\nExamples:\n`volume 70`\n`navigate to github.com`\n`weather New York`\n`sysinfo`\n`reminder call mom in 2 hours`")
                        continue

                    if text.lower() == "/status":
                        self._send("✅ Friday online")
                        continue

                    # Forward to agent
                    self._send("⚙ Processing...")
                    try:
                        reply = self.agent(text)
                        self._send(f"```\n{reply[:3900]}\n```")
                    except Exception as e:
                        self._send(f"❌ Error: {e}")

            except Exception as e:
                log.warning(f"Telegram poll error: {e}")
                time.sleep(3)

    def stop(self):
        self._stop.set()
        if self.enabled:
            self._send("⚡ Friday going offline.")
