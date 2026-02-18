"""
Friday Active Context — Conversation State Tracker

Remembers what Friday just did so follow-up commands
feel natural without repeating yourself.

Examples:
  User: "Friday, youtube volume 50"
  Friday: Volume set to 50%

  User: "increase to 100"          ← no "Friday, youtube volume" needed
  Friday: Volume set to 100%

  User: "mute it"
  Friday: Muted

  User: "what was the video about?"
  Friday: [reads page, answers]    ← remembers we're on youtube
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class ActionContext:
    """Represents the last action Friday took."""
    tool:        str            # tool name e.g. "youtube_volume"
    args:        dict           # args used e.g. {"level": 50}
    result:      str            # what happened e.g. "Volume set to 50%"
    ok:          bool           # success?
    timestamp:   datetime = field(default_factory=datetime.now)

    # Inferred context
    site:        str  = ""      # e.g. "youtube", "netflix", "gmail"
    arm:         str  = "cmd"   # "cmd" or "browser"
    subject:     str  = ""      # what was acted on e.g. "volume", "video", "tab"


# ── Tool → semantic context mapping ──────────────────────────────────────────

TOOL_CONTEXT = {
    # Volume
    "youtube_volume":       {"site": "youtube",  "subject": "volume",   "arm": "browser"},
    "volume":               {"site": "system",   "subject": "volume",   "arm": "cmd"},
    # mute_volume merged into volume tool,
    "youtube_volume_ext":   {"site": "youtube",  "subject": "volume",   "arm": "browser"},

    # YouTube
    "play_youtube":         {"site": "youtube",  "subject": "video",    "arm": "browser"},
    "pause_youtube":        {"site": "youtube",  "subject": "video",    "arm": "browser"},
    "toggle_youtube":       {"site": "youtube",  "subject": "video",    "arm": "browser"},
    "youtube_skip":         {"site": "youtube",  "subject": "position", "arm": "browser"},
    "youtube_speed":        {"site": "youtube",  "subject": "speed",    "arm": "browser"},
    "youtube_info":         {"site": "youtube",  "subject": "video",    "arm": "browser"},
    "youtube_fullscreen":   {"site": "youtube",  "subject": "display",  "arm": "browser"},
    "youtube_theater":      {"site": "youtube",  "subject": "display",  "arm": "browser"},

    # Netflix
    "toggle_netflix":       {"site": "netflix",  "subject": "video",    "arm": "browser"},
    "netflix_skip_intro":   {"site": "netflix",  "subject": "video",    "arm": "browser"},
    "netflix_next_episode": {"site": "netflix",  "subject": "video",    "arm": "browser"},

    # Navigation
    "navigate":             {"site": "",         "subject": "page",     "arm": "browser"},
    "get_url":              {"site": "",         "subject": "page",     "arm": "browser"},
    "read_page":            {"site": "",         "subject": "page",     "arm": "browser"},
    "click":                {"site": "",         "subject": "element",  "arm": "browser"},
    "fill_input":           {"site": "",         "subject": "input",    "arm": "browser"},

    # Files
    "move_file":            {"site": "system",   "subject": "file",     "arm": "cmd"},
    "copy_file":            {"site": "system",   "subject": "file",     "arm": "cmd"},
    "delete_file":          {"site": "system",   "subject": "file",     "arm": "cmd"},
    "read_file":            {"site": "system",   "subject": "file",     "arm": "cmd"},
    "write_file":           {"site": "system",   "subject": "file",     "arm": "cmd"},

    # Wifi/BT
    "connect_wifi":         {"site": "system",   "subject": "wifi",     "arm": "cmd"},
    "connect_bluetooth":    {"site": "system",   "subject": "bluetooth","arm": "cmd"},

    # Packages
    "install_package":      {"site": "system",   "subject": "package",  "arm": "cmd"},
    "uninstall_package":    {"site": "system",   "subject": "package",  "arm": "cmd"},

    # Brightness
    "set_brightness":       {"site": "system",   "subject": "brightness","arm": "cmd"},

    # Docker
    "docker_action":        {"site": "docker",   "subject": "container","arm": "cmd"},
    "docker_ps":            {"site": "docker",   "subject": "container","arm": "cmd"},

    # Search
    "web_search":           {"site": "web",      "subject": "search",   "arm": "cmd"},
}

# ── Natural language → relative adjustment patterns ─────────────────────────

VOLUME_ADJUSTMENTS = {
    # Increase
    "louder":           +15,
    "louder please":    +15,
    "a bit louder":     +10,
    "little louder":    +10,
    "more":             +15,
    "bit more":         +10,
    "little more":      +10,
    "increase":         +15,
    "up":               +15,
    "turn up":          +15,
    "bump up":          +10,
    "raise":            +15,
    "higher":           +15,

    # Decrease
    "quieter":          -15,
    "quieter please":   -15,
    "a bit quieter":    -10,
    "little quieter":   -10,
    "lower":            -15,
    "bit lower":        -10,
    "little lower":     -10,
    "decrease":         -15,
    "down":             -15,
    "turn down":        -15,
    "reduce":           -15,
    "softer":           -15,

    # Absolute
    "mute":             0,
    "mute it":          0,
    "silence":          0,
    "silent":           0,
    "max":              100,
    "maximum":          100,
    "full":             100,
    "full volume":      100,
    "half":             50,
    "halfway":          50,
}

BRIGHTNESS_ADJUSTMENTS = {
    "brighter":         +15,
    "dimmer":           -15,
    "a bit brighter":   +10,
    "a bit dimmer":     -10,
    "darker":           -15,
    "lighter":          +15,
    "increase":         +15,
    "decrease":         -15,
    "up":               +15,
    "down":             -15,
    "max":              100,
    "minimum":          10,
    "dim":              20,
    "bright":           80,
}

PLAYBACK_INTENTS = {
    "play":             "play",
    "start":            "play",
    "resume":           "play",
    "continue":         "play",
    "unpause":          "play",
    "pause":            "pause",
    "stop":             "pause",
    "freeze":           "pause",
    "hold":             "pause",
    "toggle":           "toggle",
    "play pause":       "toggle",
    "play/pause":       "toggle",
}

SKIP_PATTERNS = {
    "skip ahead":        +30,
    "skip forward":      +30,
    "skip back":         -30,
    "go forward":        +10,
    "go back":           -10,
    "skip":              +10,    # bare "skip" or "skip 30" — direction from number sign
    "forward":           +10,
    "rewind":            -10,
    "backward":          -10,
    "back":              -10,
}

SPEED_PATTERNS = {
    "faster":            0.25,   # relative increase
    "slower":           -0.25,   # relative decrease
    "normal speed":      1.0,    # absolute
    "normal":            1.0,
    "half speed":        0.5,
    "double speed":      2.0,
    "2x":                2.0,
    "1.5x":              1.5,
    "1x":                1.0,
}


class SessionContext:
    """Tracks active session state for natural follow-up commands."""

    def __init__(self):
        self.last_action:   Optional[ActionContext] = None
        self.current_site:  str   = ""
        self.current_url:   str   = ""
        self.current_title: str   = ""
        self.last_volume:   int   = 50     # system volume
        self.last_yt_vol:   int   = 100    # youtube volume (0-100)
        self.last_brightness: int = 80
        self.last_file:     str   = ""
        self.last_package:  str   = ""
        self.last_search:   str   = ""
        self.conversation:  list  = []     # recent exchanges (user, friday)

    def update(self, tool: str, args: dict, result: str, ok: bool):
        """Called after every tool execution."""
        ctx = TOOL_CONTEXT.get(tool, {})

        self.last_action = ActionContext(
            tool=tool, args=args, result=result, ok=ok,
            site=ctx.get("site", ""),
            arm=ctx.get("arm", "cmd"),
            subject=ctx.get("subject", ""),
        )

        # Update specific state
        if tool in ("volume",) and "level" in args:
            self.last_volume = args["level"]
        if tool in ("youtube_volume",) and "level" in args:
            self.last_yt_vol = args["level"]
        if tool == "set_brightness" and "level" in args:
            self.last_brightness = args["level"]
        if "path" in args:
            self.last_file = args.get("path", "")
        if "package" in args:
            self.last_package = args.get("package", "")
        if "query" in args:
            self.last_search = args.get("query", "")
        if tool == "navigate" and "url" in args:
            url = args["url"].lower()
            if "youtube" in url:   self.current_site = "youtube"
            elif "netflix" in url: self.current_site = "netflix"
            elif "gmail" in url:   self.current_site = "gmail"
            elif "twitter" in url or "x.com" in url: self.current_site = "twitter"
            elif "spotify" in url: self.current_site = "spotify"
            else: self.current_site = ""
            self.current_url = args["url"]

        # Infer site from tool
        if ctx.get("site") and ctx["site"] not in ("system", "web", "docker"):
            self.current_site = ctx["site"]

    def resolve_shorthand(self, user_input: str) -> Optional[dict]:
        """
        Try to resolve short follow-up input using active context.
        Returns {tool, args} if resolved, None if needs LLM.
        """
        text = user_input.lower().strip()

        if not self.last_action:
            return None

        subject  = self.last_action.subject
        site     = self.current_site or self.last_action.site
        last_vol = self.last_yt_vol if site == "youtube" else self.last_volume

        # ── Volume context ───────────────────────────────────────────────────
        if subject == "volume" or any(w in text for w in ["volume", "vol", "sound", "audio"]):

            # Check mute
            if any(w in text for w in ["mute", "silence", "silent"]):
                if site == "youtube":
                    return {"tool": "dom_op", "args": {"op": "video_mute"}}
                return {"tool": "volume", "args": {"action": "mute"}}

            # Check unmute
            if any(w in text for w in ["unmute", "unsilence"]):
                if site == "youtube":
                    return {"tool": "dom_op", "args": {"op": "video_unmute"}}
                return {"tool": "volume", "args": {"action": "unmute"}}

            # Exact number — but ONLY if text is clearly about volume, not speed/skip/seek
            _non_volume_words = {"skip","forward","back","rewind","seek","speed","x","faster","slower","second","sec"}
            _is_vol_context = not any(w in text.split() for w in _non_volume_words) and "x" not in text
            import re
            num_match = re.search(r'\b(\d{1,3})\b', text)
            if num_match and _is_vol_context:
                level = int(num_match.group(1))
                level = max(0, min(100, level))
                if site == "youtube":
                    return {"tool": "youtube_volume", "args": {"level": level}}
                return {"tool": "volume", "args": {"action": "set", "level": level}}

            # Relative: louder / quieter etc. — sorted longest-first to avoid "louder" eating "a bit louder"
            for phrase, delta in sorted(VOLUME_ADJUSTMENTS.items(), key=lambda x: -len(x[0])):
                if phrase in text:
                    if delta == 0:
                        if site == "youtube":
                            return {"tool": "dom_op", "args": {"op": "video_mute"}}
                        return {"tool": "volume", "args": {"action": "mute"}}
                    if delta == 100:
                        if site == "youtube":
                            return {"tool": "youtube_volume", "args": {"level": 100}}
                        return {"tool": "volume", "args": {"action": "set", "level": 100}}
                    if delta == 50:
                        if site == "youtube":
                            return {"tool": "youtube_volume", "args": {"level": 50}}
                        return {"tool": "volume", "args": {"action": "set", "level": 50}}

                    new_level = max(0, min(100, last_vol + delta))
                    if site == "youtube":
                        return {"tool": "youtube_volume", "args": {"level": new_level}}
                    return {"tool": "volume", "args": {"action": "set", "level": new_level}}

        # ── Video/playback context (youtube, netflix) ─────────────────────────
        if subject in ("video",) or site in ("youtube", "netflix", "spotify"):

            for phrase, intent in sorted(PLAYBACK_INTENTS.items(), key=lambda x: -len(x[0])):
                if phrase == text or text.startswith(phrase):
                    tool = f"{intent}_{site}" if site in ("youtube", "netflix") else f"toggle_{site}"
                    if self._tool_map_has(tool):
                        return {"tool": tool, "args": {}}
                    # Fallback to JS
                    op_map = {
                        "play":   "video_play",
                        "pause":  "video_pause",
                        "toggle": "video_toggle",
                    }
                    op = op_map.get(intent)
                    if op:
                        return {"tool": "dom_op", "args": {"op": op}}

            # Skip patterns — extract number from text first ("skip 30" → 30s)
            import re
            num_in_text = re.search(r'\b(\d+)\b', text)
            for phrase, default_secs in sorted(SKIP_PATTERNS.items(), key=lambda x: -len(x[0])):
                if phrase in text:
                    if num_in_text:
                        actual = int(num_in_text.group(1))
                        actual = actual if default_secs > 0 else -actual
                    else:
                        actual = default_secs
                    return {"tool": "dom_op", "args": {"op": "video_seek", "value": str(actual)}}

            # Speed patterns — longest-first
            for phrase, speed in sorted(SPEED_PATTERNS.items(), key=lambda x: -len(x[0])):
                if phrase in text:
                    if phrase in ("faster", "slower"):
                        last_speed = getattr(self, 'last_speed', 1.0)
                        new_speed = round(max(0.25, min(2.0, last_speed + speed)), 2)
                    else:
                        new_speed = speed
                        self.last_speed = new_speed
                    return {"tool": "dom_op", "args": {"op": "video_speed", "value": str(new_speed)}}

        # ── Brightness context ────────────────────────────────────────────────
        if subject == "brightness" or "brightness" in text or "screen" in text:
            import re
            num_match = re.search(r'\b(\d{1,3})\b', text)
            if num_match:
                level = max(0, min(100, int(num_match.group(1))))
                return {"tool": "set_brightness", "args": {"level": level}}

            for phrase, delta in sorted(BRIGHTNESS_ADJUSTMENTS.items(), key=lambda x: -len(x[0])):
                if phrase in text:
                    if isinstance(delta, int) and delta in (100, 10, 20, 80):
                        new_level = delta  # absolute
                    else:
                        new_level = max(0, min(100, self.last_brightness + delta))
                    return {"tool": "set_brightness", "args": {"level": new_level}}

        # ── File context ──────────────────────────────────────────────────────
        if subject == "file" and self.last_file:
            if "open" in text or "read" in text or "show" in text:
                return {"tool": "read_file", "args": {"path": self.last_file}}
            if "delete" in text or "remove" in text:
                return {"tool": "delete_file", "args": {"path": self.last_file}}

        return None  # Let LLM handle it

    def _tool_map_has(self, tool: str) -> bool:
        """Check if tool exists (set externally)."""
        return False  # will be overridden

    def as_prompt_context(self) -> str:
        """Build context string injected into every system prompt."""
        parts = []

        if self.last_action:
            la = self.last_action
            age = (datetime.now() - la.timestamp).seconds
            if age < 300:  # Only inject if within 5 minutes
                parts.append(
                    f"LAST ACTION: {la.tool}({la.args}) → \"{la.result[:80]}\""
                    f"  [site={la.site or 'unknown'}, subject={la.subject}]"
                )

        if self.current_site:
            parts.append(f"CURRENT SITE: {self.current_site}")
        if self.current_url:
            parts.append(f"CURRENT URL: {self.current_url}")

        # Hint about follow-up handling
        if self.last_action and self.last_action.subject == "volume":
            parts.append(
                f"VOLUME STATE: system={self.last_volume}%, "
                f"youtube={self.last_yt_vol}%"
            )
        if self.last_action and self.last_action.subject == "brightness":
            parts.append(f"BRIGHTNESS STATE: {self.last_brightness}%")

        if parts:
            parts.append(
                "\nFOLLOW-UP RULE: The user may give short follow-up commands without repeating context. "
                "e.g. after setting youtube volume, 'increase to 100' means youtube_volume 100. "
                "'louder' means increase current volume. 'pause' means pause current site's video. "
                "Always use the active context to infer the full intent."
            )

        return "\n".join(parts)


# Global singleton
session = SessionContext()
