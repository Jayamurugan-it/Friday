"""
Friday Multi-Step Task Planner
Decomposes complex user instructions into ordered tool steps
before execution. Used by agent for long-horizon tasks.
"""

import os
import json
import re
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Step:
    order:       int
    description: str
    tool:        str
    args:        dict = field(default_factory=dict)
    depends_on:  list = field(default_factory=list)


@dataclass
class Plan:
    goal:     str
    steps:    list
    parallel: bool = False


# ── Heuristic local planner (no LLM call needed for common patterns) ──────────

_PATTERNS = [
    # "install X and Y" → two install steps
    (r"install (\w[\w-]*) (?:and|&) (\w[\w-]*)", lambda m: [
        Step(1, f"Install {m.group(1)}", "install_package", {"package": m.group(1)}),
        Step(2, f"Install {m.group(2)}", "install_package", {"package": m.group(2)}),
    ]),
    # "move X to Y then open it" → move + launch
    (r"move (.+?) to (.+?) (?:then |and )?open it", lambda m: [
        Step(1, f"Move file", "move_file", {"source": m.group(1).strip(), "destination": m.group(2).strip()}),
        Step(2, f"Open file", "launch_app", {"app_name": m.group(2).strip()}),
    ]),
    # "zip/archive folder X and upload to Y" → archive + navigate
    (r"(?:zip|archive) (.+?) (?:and (?:upload|send) to) (.+)", lambda m: [
        Step(1, f"Archive {m.group(1)}", "archive_files",
             {"path": m.group(1).strip(), "output": m.group(1).strip() + ".zip"}),
        Step(2, f"Navigate to {m.group(2)}", "navigate",
             {"url": m.group(2).strip() if "http" in m.group(2) else "https://" + m.group(2).strip()}),
    ]),
    # "connect wifi X then bluetooth Y" → two connects
    (r"connect (?:to )?wifi (.+?) (?:then|and) (?:connect )?(?:to )?bluetooth (.+)", lambda m: [
        Step(1, f"Connect WiFi {m.group(1)}", "connect_wifi", {"ssid": m.group(1).strip()}, parallel=False),
        Step(2, f"Connect BT {m.group(2)}", "connect_bluetooth",
             {"name_or_mac": m.group(2).strip()}, depends_on=[1]),
    ]),
    # "search X and open first result"
    (r"search (?:for )?(.+?) and open (?:the )?first (?:result|link)", lambda m: [
        Step(1, f"Search {m.group(1)}", "web_search", {"query": m.group(1).strip()}),
        Step(2, "Open first result", "navigate", {"url": "RESULT_FROM_STEP_1"}),
    ]),
    # "read file X and summarize" / "read X and tell me"
    (r"(?:read|open|show) (?:file )?(.+?) and (?:summarize|tell|explain|describe)", lambda m: [
        Step(1, f"Read {m.group(1)}", "read_file", {"path": m.group(1).strip()}),
        Step(2, "Summarize content", "_llm_summarize", {"source_step": 1}),
    ]),
]


def local_plan(task: str) -> Optional[Plan]:
    """Try to build a plan from simple heuristic patterns."""
    task_lower = task.lower().strip()
    for pattern, builder in _PATTERNS:
        m = re.search(pattern, task_lower)
        if m:
            steps = builder(m)
            return Plan(goal=task, steps=steps)
    return None


# ── LLM planner (for complex multi-step tasks) ─────────────────────────────────

PLANNER_SYSTEM = """You are Friday's task planner.
Given a complex user task, decompose it into concrete ordered steps.
Return ONLY a JSON object:
{
  "goal": "...",
  "parallel": false,
  "steps": [
    {"order": 1, "tool": "tool_name", "args": {}, "description": "..."},
    {"order": 2, "tool": "tool_name", "args": {}, "description": "...", "depends_on": [1]}
  ]
}

Available tool categories:
- System: get_volume, set_volume, connect_wifi, connect_bluetooth, move_file, copy_file,
  install_package, service_action, system_info, disk_usage, get_ip, list_processes
- Browser: navigate, click, fill_input, fill_form, get_text, read_page, auto_login,
  start_recording, stop_recording, replay_session, get_tabs, close_tab
- Web: web_search, fetch_page, get_weather, get_stock, calculate, convert_currency
- Memory: remember_fact, add_reminder_nlp, create_goal, save_note
- Meta: show_history, db_stats, undo_last

Rules:
- steps that can run in parallel: set parallel=true and omit depends_on
- max 8 steps
- args must match exact tool signatures
- if a step uses output from a previous step, note it in description
"""


def llm_plan(task: str, client, model: str) -> Optional[Plan]:
    """Use LLM to decompose a complex task into steps."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM},
                {"role": "user",   "content": f"Task: {task}"},
            ],
            max_tokens=1024,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content or ""
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$",          "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        steps = [
            Step(
                order=s["order"],
                description=s.get("description", ""),
                tool=s.get("tool", ""),
                args=s.get("args", {}),
                depends_on=s.get("depends_on", []),
            )
            for s in data.get("steps", [])
        ]
        return Plan(goal=task, steps=steps, parallel=data.get("parallel", False))
    except Exception:
        return None


# ── Complexity scorer — decides if planning is needed ─────────────────────────

_MULTI_INDICATORS = [
    "then", "and then", "after that", "next", "finally", "first",
    "step 1", "step 2", " and ", " also ", "followed by",
    "then open", "then click", "then fill", "then save",
]

_COMPLEX_VERBS = [
    "deploy", "migrate", "backup", "setup", "configure",
    "automate", "workflow", "pipeline",
]


def needs_planning(task: str) -> bool:
    """Heuristic: should this task be pre-planned?"""
    task_lower = task.lower()
    multi = sum(1 for i in _MULTI_INDICATORS if i in task_lower)
    complex_ = any(v in task_lower for v in _COMPLEX_VERBS)
    word_count = len(task.split())
    return multi >= 2 or complex_ or word_count > 20


def format_plan(plan: Plan) -> str:
    """Render a plan as a human-readable string for confirmation."""
    lines = [f"📋 Plan: {plan.goal}", f"   {len(plan.steps)} steps{'  (parallel)' if plan.parallel else ''}:", ""]
    for s in plan.steps:
        dep = f"  after step {s.depends_on}" if s.depends_on else ""
        lines.append(f"  {s.order}. {s.description}  [{s.tool}]{dep}")
    return "\n".join(lines)
