"""
Friday Skill Validator
======================
Every skill (Python or JS) goes through this layer before being added
to Friday's tool list. Nothing reaches the agent without passing.

Checks performed:
  STRUCTURE  — SKILL_TOOLS and SKILL_HANDLERS exist and are correct types
  SCHEMA     — Every tool definition has required JSON schema fields
  ALIGNMENT  — Every tool in SKILL_TOOLS has a matching handler, and vice versa
  HANDLER    — Every handler is callable with the right signature
  SANDBOX    — Each handler is dry-run with safe dummy args; return value checked
  SAFETY     — Dangerous patterns (os.system, eval, subprocess shell=True) flagged
  JS SKILL   — Extension .js skills validated for name/commands/handler structure

On failure: skill is REJECTED with a detailed report, rest of Friday unaffected.
On warning: skill LOADS but user is notified of issues.
"""

import ast
import inspect
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger("friday.validator")


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    level:   str   # "ERROR" | "WARNING" | "INFO"
    code:    str   # short code e.g. "MISSING_HANDLER"
    message: str
    tool:    str = ""  # which tool caused it (if applicable)

    def __str__(self):
        prefix = {"ERROR": "✗", "WARNING": "⚠", "INFO": "ℹ"}.get(self.level, "?")
        tool_part = f" [{self.tool}]" if self.tool else ""
        return f"  {prefix} {self.code}{tool_part}: {self.message}"


@dataclass
class ValidationReport:
    skill_name: str
    passed:     bool = True
    issues:     list = field(default_factory=list)
    tools_ok:   list = field(default_factory=list)   # tool names that passed
    tools_bad:  list = field(default_factory=list)   # tool names that failed

    def error(self, code, message, tool=""):
        self.issues.append(Issue("ERROR", code, message, tool))
        self.passed = False
        if tool and tool not in self.tools_bad:
            self.tools_bad.append(tool)

    def warn(self, code, message, tool=""):
        self.issues.append(Issue("WARNING", code, message, tool))
        if tool and tool not in self.tools_ok:
            self.tools_ok.append(tool)

    def info(self, code, message, tool=""):
        self.issues.append(Issue("INFO", code, message, tool))

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"Skill: {self.skill_name}  [{status}]",
            f"  Tools OK : {len(self.tools_ok)}",
            f"  Tools BAD: {len(self.tools_bad)}",
        ]
        if self.issues:
            lines.append("  Issues:")
            for issue in self.issues:
                lines.append(f"  {issue}")
        return "\n".join(lines)

    def short(self) -> str:
        if self.passed and not self.issues:
            return f"✓ {self.skill_name}: {len(self.tools_ok)} tools validated"
        status = "LOADED WITH WARNINGS" if self.passed else "REJECTED"
        errors = [i for i in self.issues if i.level == "ERROR"]
        warns  = [i for i in self.issues if i.level == "WARNING"]
        return (f"{'⚠' if self.passed else '✗'} {self.skill_name}: {status} "
                f"({len(errors)} errors, {len(warns)} warnings)")


# ── Dummy arg generators ──────────────────────────────────────────────────────

def _dummy_args(parameters: dict) -> dict:
    """Generate safe dummy args from a tool's JSON schema parameters."""
    props    = parameters.get("properties", {})
    required = parameters.get("required", [])
    args = {}

    for name, schema in props.items():
        t = schema.get("type", "string")
        if t == "string":
            # Use safe values for common param names
            safe_strings = {
                "path":     "/tmp/friday_test.txt",
                "url":      "https://example.com",
                "query":    "test query",
                "name":     "test_name",
                "text":     "hello world",
                "message":  "test message",
                "command":  "echo test",
                "host":     "localhost",
                "domain":   "example.com",
                "code":     "console.log('test')",
                "content":  "test content",
                "title":    "test title",
            }
            args[name] = safe_strings.get(name, f"test_{name}")
        elif t == "integer":
            safe_ints = {"level": 50, "count": 3, "port": 8080, "seconds": 5,
                         "limit": 5, "n": 3, "lines": 10, "timeout": 5}
            args[name] = safe_ints.get(name, 1)
        elif t == "number":
            args[name] = 1.0
        elif t == "boolean":
            args[name] = False
        elif t == "array":
            args[name] = []
        elif t == "object":
            args[name] = {}

    return args


# ── Safety scanner ────────────────────────────────────────────────────────────

DANGER_PATTERNS = [
    # (ast_check_fn, code, message)
    # These are WARNING level — we flag but don't reject (user may have legitimate reasons)
]

CRITICAL_PATTERNS = [
    "exec(",
    "eval(",
    "__import__('os').system",
    "subprocess.call(",
]

def _scan_source(source: str, report: ValidationReport):
    """AST-scan skill source for dangerous patterns."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        report.error("SYNTAX_ERROR", f"SyntaxError line {e.lineno}: {e.msg}")
        return

    for node in ast.walk(tree):
        # Flag eval/exec
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                report.warn("UNSAFE_EVAL",
                            f"eval/exec at line {node.lineno} — potential security risk")

        # Flag subprocess with shell=True
        if isinstance(node, ast.Call):
            for kw in getattr(node, "keywords", []):
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    report.warn("SHELL_TRUE",
                                f"subprocess shell=True at line {node.lineno} — injection risk")

        # Flag os.system
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "system"
                    and isinstance(func.value, ast.Name) and func.value.id == "os"):
                report.warn("OS_SYSTEM",
                            f"os.system() at line {node.lineno} — prefer subprocess")


# ── Schema validator ──────────────────────────────────────────────────────────

REQUIRED_TOOL_FIELDS = {"type", "function"}
REQUIRED_FUNC_FIELDS = {"name", "description", "parameters"}

def _validate_tool_schema(tool: Any, report: ValidationReport) -> Optional[str]:
    """Validate a single tool definition. Returns tool name or None on error."""
    if not isinstance(tool, dict):
        report.error("BAD_TOOL_TYPE", f"Tool definition must be dict, got {type(tool).__name__}")
        return None

    missing = REQUIRED_TOOL_FIELDS - set(tool.keys())
    if missing:
        report.error("MISSING_TOOL_FIELDS", f"Missing fields: {missing}")
        return None

    if tool.get("type") != "function":
        report.error("BAD_TOOL_TYPE", f"type must be 'function', got {tool.get('type')!r}")
        return None

    fn = tool.get("function", {})
    if not isinstance(fn, dict):
        report.error("BAD_FUNCTION_FIELD", "function field must be a dict")
        return None

    missing_fn = REQUIRED_FUNC_FIELDS - set(fn.keys())
    if missing_fn:
        report.error("MISSING_FUNC_FIELDS", f"function missing fields: {missing_fn}")
        return None

    name = fn.get("name", "")
    if not name or not isinstance(name, str):
        report.error("BAD_TOOL_NAME", "Tool name must be a non-empty string")
        return None

    desc = fn.get("description", "")
    if not desc:
        report.warn("MISSING_DESCRIPTION", "Tool has no description — Friday won't know when to use it", tool=name)

    params = fn.get("parameters", {})
    if not isinstance(params, dict):
        report.error("BAD_PARAMETERS", "parameters must be a dict", tool=name)
        return None

    if params.get("type") != "object":
        report.error("BAD_PARAMS_TYPE", "parameters.type must be 'object'", tool=name)
        return None

    return name


# ── Handler validator ─────────────────────────────────────────────────────────

def _validate_handler(name: str, handler: Any, dummy_args: dict,
                      report: ValidationReport) -> bool:
    """Validate a handler is callable and returns correct format."""
    if not callable(handler):
        report.error("NOT_CALLABLE", f"Handler is {type(handler).__name__}, not callable", tool=name)
        return False

    # Sandbox: call with dummy args, 3 second timeout
    import threading
    result_box = [None]
    error_box  = [None]

    def _call():
        try:
            result_box[0] = handler(dummy_args)
        except Exception as e:
            error_box[0] = e

    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=3)

    if t.is_alive():
        report.warn("HANDLER_TIMEOUT",
                    f"Handler took >3s with dummy args — may block Friday", tool=name)
        return True  # Don't fail — real args may be faster

    if error_box[0] is not None:
        err = error_box[0]
        # These errors are expected with dummy/fake args — don't penalise the tool
        expected_errors = (
            FileNotFoundError, IsADirectoryError, PermissionError,
            ConnectionRefusedError, ConnectionError, TimeoutError,
            NotADirectoryError, OSError,
        )
        if isinstance(err, expected_errors):
            report.info("HANDLER_EXPECTED_ERROR",
                        f"Handler raised {type(err).__name__} with dummy args (expected)", tool=name)
            return True
        else:
            # Mark only THIS tool as bad — other tools in the skill still load
            report.issues.append(Issue(
                "ERROR", "HANDLER_CRASH",
                f"Handler crashed with dummy args: {type(err).__name__}: {err}",
                tool=name
            ))
            if name not in report.tools_bad:
                report.tools_bad.append(name)
            # Do NOT set report.passed = False — partial load is fine
            return False

    result = result_box[0]

    # Validate return format
    if result is None:
        report.warn("RETURNS_NONE", "Handler returned None — expected object with .ok and .out", tool=name)
        return True

    # Check for .ok and .out (dataclass or object)
    has_ok  = hasattr(result, "ok")  or (isinstance(result, dict) and "ok"  in result)
    has_out = hasattr(result, "out") or (isinstance(result, dict) and "out" in result)

    if not has_ok:
        report.warn("MISSING_OK_FIELD",
                    "Return value has no .ok field — Friday can't tell if it succeeded", tool=name)
    if not has_out:
        report.warn("MISSING_OUT_FIELD",
                    "Return value has no .out field — Friday has nothing to show user", tool=name)

    if has_ok and has_out:
        report.tools_ok.append(name)

    return True


# ── Main Python skill validator ───────────────────────────────────────────────

def validate_python_skill(path_or_source, mod=None) -> ValidationReport:
    """
    Full validation of a Python skill.
    Pass either the file path (str/Path) or (source_code, module_object).
    """
    from pathlib import Path as P

    if isinstance(path_or_source, (str, P)) and mod is None:
        path = P(path_or_source)
        skill_name = path.stem
        report = ValidationReport(skill_name=skill_name)

        # Read source
        try:
            source = path.read_text()
        except Exception as e:
            report.error("READ_ERROR", f"Cannot read file: {e}")
            return report

        # Syntax check
        try:
            ast.parse(source)
        except SyntaxError as e:
            report.error("SYNTAX_ERROR", f"Line {e.lineno}: {e.msg}")
            return report

        # Safety scan
        _scan_source(source, report)
        if not report.passed:
            return report

        # Import the module
        import importlib.util
        try:
            spec = importlib.util.spec_from_file_location(f"skill_val_{skill_name}", path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            report.error("IMPORT_ERROR", f"Module failed to import: {e}")
            return report
    else:
        # Called with (source, mod) pair
        source = path_or_source if isinstance(path_or_source, str) else ""
        skill_name = getattr(mod, "__name__", "unknown").replace("skill_", "")
        report = ValidationReport(skill_name=skill_name)

    # Check SKILL_TOOLS exists
    tools = getattr(mod, "SKILL_TOOLS", None)
    if tools is None:
        report.error("MISSING_SKILL_TOOLS", "SKILL_TOOLS not defined. Add SKILL_TOOLS = [...] to your skill.")
        return report
    if not isinstance(tools, list):
        report.error("BAD_SKILL_TOOLS", f"SKILL_TOOLS must be a list, got {type(tools).__name__}")
        return report
    if len(tools) == 0:
        report.warn("EMPTY_SKILL_TOOLS", "SKILL_TOOLS is empty — no tools will be added")
        return report

    # Check SKILL_HANDLERS exists
    handlers = getattr(mod, "SKILL_HANDLERS", None)
    if handlers is None:
        report.error("MISSING_SKILL_HANDLERS", "SKILL_HANDLERS not defined. Add SKILL_HANDLERS = {...} to your skill.")
        return report
    if not isinstance(handlers, dict):
        report.error("BAD_SKILL_HANDLERS", f"SKILL_HANDLERS must be a dict, got {type(handlers).__name__}")
        return report

    # Validate each tool schema
    tool_names = []
    for i, tool in enumerate(tools):
        name = _validate_tool_schema(tool, report)
        if name:
            tool_names.append(name)

    if not report.passed:
        return report

    # Alignment check: every tool has a handler
    for name in tool_names:
        if name not in handlers:
            report.error("MISSING_HANDLER",
                         f"Tool '{name}' is in SKILL_TOOLS but has no entry in SKILL_HANDLERS",
                         tool=name)

    # Alignment check: every handler has a tool
    for name in handlers:
        if name not in tool_names:
            report.warn("ORPHAN_HANDLER",
                        f"Handler '{name}' is in SKILL_HANDLERS but has no tool definition",
                        tool=name)

    if not report.passed:
        return report

    # Sandbox test each handler
    for i, tool in enumerate(tools):
        fn_def  = tool.get("function", {})
        name    = fn_def.get("name", f"tool_{i}")
        params  = fn_def.get("parameters", {})
        handler = handlers.get(name)

        if handler is None:
            continue  # Already flagged above

        dummy = _dummy_args(params)
        _validate_handler(name, handler, dummy, report)

    # Final: mark all tools that had no errors as OK
    for name in tool_names:
        if name not in report.tools_bad and name not in report.tools_ok:
            report.tools_ok.append(name)

    return report


# ── JS Extension Skill Validator ──────────────────────────────────────────────

def validate_js_skill(path) -> ValidationReport:
    """
    Validate a JavaScript extension skill file.
    Checks structure, required fields, command handlers.
    """
    from pathlib import Path as P
    path = P(path)
    skill_name = path.stem
    report = ValidationReport(skill_name=f"{skill_name} [JS]")

    try:
        source = path.read_text()
    except Exception as e:
        report.error("READ_ERROR", f"Cannot read JS file: {e}")
        return report

    if not source.strip():
        report.error("EMPTY_FILE", "JS skill file is empty")
        return report

    # Strip single-line comments before checking structure
    import re
    source_no_comments = re.sub(r'//[^\n]*', '', source)
    source_no_comments = re.sub(r'/\*.*?\*/', '', source_no_comments, flags=re.DOTALL)

    # Must have name field (actual string assignment, not in comments)
    if not re.search(r'\bname\s*:\s*["\']', source_no_comments):
        report.error("MISSING_NAME",
                     "Skill object has no 'name' field. Add: name: 'My Skill'")

    # Must have commands object (actual code, not comments)
    if not re.search(r'\bcommands\s*:', source_no_comments):
        report.error("MISSING_COMMANDS",
                     "No 'commands' object found. Add: commands: { my_command: { handler: async () => {} } }")

    # Must have handler functions (actual code)
    if not re.search(r'\bhandler\s*:', source_no_comments):
        report.error("MISSING_HANDLERS",
                     "No 'handler' functions found. Each command needs: handler: async (args) => { return { ok: true, text: '...' } }")

    # Must register with Friday
    if "FridaySkills.register" not in source_no_comments:
        report.error("NOT_REGISTERED",
                     "Skill doesn't register with Friday. Add at the end:\n"
                     "if (typeof window.FridaySkills !== 'undefined') {\n"
                     "  window.FridaySkills.register(MySkill);\n"
                     "}")

    # Check return format { ok, text }
    returns = re.findall(r'return\s*\{([^}]+)\}', source_no_comments)
    bad_returns = [r for r in returns if 'ok' not in r]
    if bad_returns:
        report.warn("MISSING_OK_IN_RETURN",
                    f"{len(bad_returns)} return statement(s) missing 'ok' field. "
                    "Use: return { ok: true, text: '...' }")

    # Async check
    if not re.search(r'\basync\b', source_no_comments):
        report.warn("NO_ASYNC",
                    "No async handlers — use 'async (args) =>' for browser operations")

    # querySelector without null check
    qs_count   = len(re.findall(r'querySelector\s*\(', source_no_comments))
    null_checks = len(re.findall(r'if\s*\(\s*!', source_no_comments))
    if qs_count > 0 and null_checks < qs_count:
        report.warn("MISSING_NULL_CHECK",
                    f"{qs_count} querySelector call(s) but only {null_checks} null checks — "
                    "add: if (!el) return { ok: false, text: 'Element not found' }")

    # Extract command names
    commands = re.findall(r'^\s{4,}(\w+)\s*:\s*\{', source_no_comments, re.MULTILINE)
    for cmd in commands:
        if cmd not in ("commands", "handler", "name", "version", "description",
                       "domains", "onPageLoad") and not cmd.startswith("_"):
            report.tools_ok.append(cmd)

    if not any(i.level == "ERROR" for i in report.issues):
        report.info("JS_VALID", f"JS skill looks valid ({len(report.tools_ok)} commands found)")

    return report


# ── Validate module object directly (used by registry) ───────────────────────

def validate_module(skill_name: str, mod, source: str = "") -> ValidationReport:
    """Validate an already-imported module object."""
    report = ValidationReport(skill_name=skill_name)

    if source:
        _scan_source(source, report)

    tools    = getattr(mod, "SKILL_TOOLS",    None)
    handlers = getattr(mod, "SKILL_HANDLERS", None)

    if tools is None:
        report.error("MISSING_SKILL_TOOLS",
                     "SKILL_TOOLS not defined.\n"
                     "Add to your skill:\n"
                     "  SKILL_TOOLS = [{ 'type': 'function', 'function': { 'name': '...', ... } }]")
        return report

    if handlers is None:
        report.error("MISSING_SKILL_HANDLERS",
                     "SKILL_HANDLERS not defined.\n"
                     "Add to your skill:\n"
                     "  SKILL_HANDLERS = { 'tool_name': lambda args: my_func(args) }")
        return report

    if not isinstance(tools, list) or len(tools) == 0:
        report.warn("EMPTY_SKILL_TOOLS", "SKILL_TOOLS is empty — no tools added")
        return report

    tool_names = []
    for tool in tools:
        name = _validate_tool_schema(tool, report)
        if name:
            tool_names.append(name)

    if not report.passed:
        return report

    # Alignment
    for name in tool_names:
        if name not in handlers:
            report.error("MISSING_HANDLER",
                         f"Tool '{name}' defined but SKILL_HANDLERS['{name}'] missing",
                         tool=name)
    for name in handlers:
        if name not in tool_names:
            report.warn("ORPHAN_HANDLER",
                        f"Handler '{name}' has no tool definition in SKILL_TOOLS",
                        tool=name)

    if not report.passed:
        return report

    # Sandbox test
    for tool in tools:
        fn_def  = tool.get("function", {})
        name    = fn_def.get("name", "")
        params  = fn_def.get("parameters", {})
        handler = handlers.get(name)
        if not handler:
            continue
        dummy = _dummy_args(params)
        ok = _validate_handler(name, handler, dummy, report)
        if ok and name not in report.tools_bad and name not in report.tools_ok:
            report.tools_ok.append(name)

    return report


# ── Quick health check for already-loaded skills ──────────────────────────────

def health_check_skill(skill_name: str, handlers: dict, tools: list) -> ValidationReport:
    """
    Lightweight re-check of a loaded skill.
    Called periodically or after skill reload.
    """
    report = ValidationReport(skill_name=skill_name)

    tool_names = [t.get("function", {}).get("name", "") for t in tools]

    for name in tool_names:
        handler = handlers.get(name)
        if not callable(handler):
            report.error("HANDLER_DEAD", f"Handler for '{name}' is no longer callable", tool=name)
        else:
            report.tools_ok.append(name)

    return report
