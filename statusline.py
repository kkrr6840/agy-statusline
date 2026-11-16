#!/usr/bin/env python3
"""Lightweight, zero-dependency statusLine renderer for Google Antigravity CLI (agy).

Reads session telemetry JSON from stdin (provided natively by agy) and local Git
HEAD/status, printing a compact two-line ANSI HUD:
  Line 1: Current directory | Git branch & dirty/ahead/behind | Context window bar (85% alert)
  Line 2: Quota overview (Gemini 5h/weekly, Argon weekly, Claude/GPT 5h/weekly)

Zero external packages, zero network requests, zero credential access.
"""

import datetime
import json
import os
import subprocess
import sys

# Ensure UTF-8 I/O even under Windows cmd.exe (GBK/cp936) pipes
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NO_COLOR = bool(os.environ.get("NO_COLOR"))

RESET = "" if NO_COLOR else "\033[0m"
DIM = "" if NO_COLOR else "\033[2m"
BOLD = "" if NO_COLOR else "\033[1m"
CYAN = "" if NO_COLOR else "\033[36m"
GREEN = "" if NO_COLOR else "\033[32m"
YELLOW = "" if NO_COLOR else "\033[33m"
RED = "" if NO_COLOR else "\033[91m"
MAGENTA = "" if NO_COLOR else "\033[35m"

SEP = f" {DIM}│{RESET} "


def fmt_tokens(n):
    if not n or n <= 0:
        return "0"
    if n >= 1_000_000:
        val = n / 1_000_000.0
        return f"{val:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        val = n / 1_000.0
        return f"{val:.0f}k" if val >= 10 else f"{val:.1f}k".replace(".0k", "k")
    return str(int(n))


def fmt_duration(seconds):
    if seconds is None:
        return ""
    try:
        sec = int(seconds)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    if sec < 60:
        return "<1m"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 36000:
        h, rem = divmod(sec, 3600)
        m = rem // 60
        return f"{h}h{m}m" if m else f"{h}h"
    if sec < 86400:
        return f"{sec // 3600}h"
    d, rem = divmod(sec, 86400)
    h = rem // 3600
    return f"{d}d{h}h" if h else f"{d}d"


def make_bar(fraction, width=10):
    f = max(0.0, min(1.0, float(fraction)))
    filled = int(round(f * width))
    return "█" * filled + "░" * (width - filled)


def format_dir(raw_dir):
    if not raw_dir:
        return "~"
    norm = os.path.normpath(raw_dir)
    home = os.path.normpath(os.path.expanduser("~"))

    is_win = os.name == "nt"
    norm_cmp = norm.lower() if is_win else norm
    home_cmp = home.lower() if is_win else home

    if norm_cmp == home_cmp:
        return "~"

    prefix = home_cmp + os.sep
    if norm_cmp.startswith(prefix):
        rel = norm[len(home) + 1 :]
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        if len(parts) <= 2:
            return "~/" + "/".join(parts)
        return "~/…/" + "/".join(parts[-2:])

    parts = [p for p in norm.replace("\\", "/").split("/") if p]
    if len(parts) <= 2:
        return norm.replace("\\", "/")
    return "…/" + "/".join(parts[-2:])


def find_git_dir(start_dir):
    """Walk up parent directories to locate .git without spawning subprocesses for non-repos."""
    cur = os.path.abspath(start_dir)
    while True:
        dot_git = os.path.join(cur, ".git")
        if os.path.isdir(dot_git):
            return cur, dot_git
        if os.path.isfile(dot_git):
            try:
                with open(dot_git, "r", encoding="utf-8", errors="replace") as f:
                    line = f.readline().strip()
                if line.startswith("gitdir:"):
                    gdir = line[7:].strip()
                    if not os.path.isabs(gdir):
                        gdir = os.path.normpath(os.path.join(cur, gdir))
                    return cur, gdir
            except OSError:
                return cur, None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None, None
        cur = parent


def read_head_branch(git_dir):
    if not git_dir:
        return None
    head_path = os.path.join(git_dir, "HEAD")
    try:
        with open(head_path, "r", encoding="utf-8", errors="replace") as f:
            head = f.readline().strip()
    except OSError:
        return None
    if head.startswith("ref: refs/heads/"):
        return head[16:]
    if head.startswith("ref: "):
        return head.split("/")[-1]
    if len(head) >= 7:
        return "@" + head[:7]
    return None


def get_git_segment(target_dir, vcs_payload):
    if not target_dir or not os.path.isdir(target_dir):
        if isinstance(vcs_payload, dict) and vcs_payload.get("branch"):
            b = vcs_payload["branch"]
            mark = "*" if vcs_payload.get("dirty") else ""
            color = YELLOW if mark else GREEN
            return f"{color}⎇ {b}{mark}{RESET}"
        return ""

    repo_root, git_dir = find_git_dir(target_dir)
    if not repo_root:
        return ""

    branch = read_head_branch(git_dir)
    dirty = False
    untracked = False
    ahead = 0
    behind = 0

    try:
        proc = subprocess.run(
            ["git", "-C", target_dir, "--no-optional-locks", "status", "--porcelain=v1", "-b"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=0.18,
        )
        if proc.returncode == 0:
            lines = proc.stdout.splitlines()
            if lines and lines[0].startswith("## "):
                header = lines[0][3:]
                if not branch or branch.startswith("@"):
                    for prefix in ("No commits yet on ", "Initial commit on "):
                        if header.startswith(prefix):
                            branch = header[len(prefix) :].strip()
                if "[" in header and header.endswith("]"):
                    meta = header[header.rfind("[") + 1 : -1]
                    for part in meta.split(","):
                        p = part.strip()
                        if p.startswith("ahead "):
                            try:
                                ahead = int(p[6:])
                            except ValueError:
                                pass
                        elif p.startswith("behind "):
                            try:
                                behind = int(p[7:])
                            except ValueError:
                                pass
            for item in lines[1:]:
                if not item:
                    continue
                if item.startswith("??"):
                    untracked = True
                else:
                    dirty = True
    except (OSError, subprocess.SubprocessError):
        pass

    if not branch:
        branch = "HEAD"

    marks = ("*" if dirty else "") + ("?" if untracked else "")
    sync = ""
    if ahead:
        sync += f" ↑{ahead}"
    if behind:
        sync += f" ↓{behind}"

    color = YELLOW if (dirty or untracked) else GREEN
    return f"{color}⎇ {branch}{marks}{sync}{RESET}"


def format_context_segment(cw, warn_pct=85.0):
    if not isinstance(cw, dict):
        cw = {}

    used_pct = cw.get("used_percentage")
    if used_pct is None:
        used_pct = 0.0
    try:
        used_pct = max(0.0, float(used_pct))
    except (TypeError, ValueError):
        used_pct = 0.0

    win_size = cw.get("context_window_size") or 0
    cu = cw.get("current_usage")
    cur_tokens = 0
    if isinstance(cu, dict):
        cur_tokens = (
            (cu.get("input_tokens") or 0)
            + (cu.get("output_tokens") or 0)
            + (cu.get("cache_creation_input_tokens") or 0)
            + (cu.get("cache_read_input_tokens") or 0)
        )
    elif used_pct > 0 and win_size > 0:
        cur_tokens = int(round(win_size * (used_pct / 100.0)))

    if used_pct >= warn_pct:
        color = RED
    elif used_pct >= 65.0:
        color = YELLOW
    else:
        color = GREEN

    bar = make_bar(used_pct / 100.0, width=10)
    pct_str = f"{used_pct:.0f}%"

    detail = ""
    if win_size > 0 and cur_tokens > 0:
        detail = f" {DIM}({fmt_tokens(cur_tokens)}/{fmt_tokens(win_size)}){RESET}"
    elif cur_tokens > 0:
        detail = f" {DIM}({fmt_tokens(cur_tokens)}){RESET}"

    alert = f" {BOLD}{RED}⚠建议交接{RESET}" if used_pct >= warn_pct else ""
    return f"{DIM}上下文{RESET} {color}[{bar}] {pct_str}{RESET}{detail}{alert}"


def resolve_reset_seconds(bucket):
    sec = bucket.get("reset_in_seconds")
    if sec is not None:
        return sec
    rt = bucket.get("reset_time")
    if not rt or not isinstance(rt, str):
        return None
    try:
        iso = rt.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(iso)
        now = datetime.datetime.now(datetime.timezone.utc)
        return max(0, int((dt - now).total_seconds()))
    except ValueError:
        return None


def fmt_quota_item(label, bucket, show_bar=True):
    if not isinstance(bucket, dict) or bucket.get("disabled") is True:
        return None
    rem = bucket.get("remaining_fraction")
    if rem is None:
        return None
    try:
        rem_f = max(0.0, min(1.0, float(rem)))
    except (TypeError, ValueError):
        return None

    pct = int(round(rem_f * 100))
    if pct <= 15:
        color = RED
    elif pct <= 40:
        color = YELLOW
    else:
        color = GREEN

    bar_part = f"[{make_bar(rem_f, width=5)}] " if show_bar else ""
    dur = fmt_duration(resolve_reset_seconds(bucket))
    dur_part = f"{DIM}({dur}){RESET}" if dur else ""
    return f"{label} {color}{bar_part}{pct}%{RESET}{dur_part}"


def format_quota_line(quota, term_width=120):
    if not isinstance(quota, dict) or not quota:
        return ""

    show_bar = term_width >= 105
    groups = []

    gemini_items = []
    for key, label in (
        ("gemini-5h", "5h"),
        ("gemini-weekly", "周"),
        ("gemini-argon-wtu-weekly", "Argon周"),
    ):
        rendered = fmt_quota_item(label, quota.get(key), show_bar=show_bar)
        if rendered:
            gemini_items.append(rendered)
    if gemini_items:
        groups.append(f"{CYAN}Gemini{RESET} " + f" {DIM}·{RESET} ".join(gemini_items))

    tp_items = []
    for key, label in (("3p-5h", "5h"), ("3p-weekly", "周")):
        rendered = fmt_quota_item(label, quota.get(key), show_bar=show_bar)
        if rendered:
            tp_items.append(rendered)
    if tp_items:
        groups.append(f"{MAGENTA}Claude/GPT{RESET} " + f" {DIM}·{RESET} ".join(tp_items))

    known = {
        "gemini-5h",
        "gemini-weekly",
        "gemini-argon-wtu-weekly",
        "3p-5h",
        "3p-weekly",
    }
    extra_items = []
    for key in sorted(quota.keys()):
        if key in known:
            continue
        rendered = fmt_quota_item(key, quota.get(key), show_bar=False)
        if rendered:
            extra_items.append(rendered)
    if extra_items:
        groups.append(f" {DIM}·{RESET} ".join(extra_items))

    if not groups:
        return ""
    return f"{DIM}配额{RESET}  " + SEP.join(groups)


def render(payload):
    if not isinstance(payload, dict):
        payload = {}

    ws = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else {}
    raw_dir = ws.get("current_dir") or payload.get("cwd") or os.getcwd()
    term_width = payload.get("terminal_width") or 120
    try:
        term_width = int(term_width)
    except (TypeError, ValueError):
        term_width = 120

    warn_pct = 85.0
    env_warn = os.environ.get("AGY_STATUSLINE_WARN_PCT")
    if env_warn:
        try:
            warn_pct = float(env_warn)
        except ValueError:
            pass

    line1_parts = [f"{CYAN}{format_dir(raw_dir)}{RESET}"]

    git_seg = get_git_segment(raw_dir, payload.get("vcs"))
    if git_seg:
        line1_parts.append(git_seg)

    if os.environ.get("AGY_STATUSLINE_SHOW_MODEL") == "1" or "--show-model" in sys.argv[1:]:
        model_obj = payload.get("model")
        if isinstance(model_obj, dict):
            mname = model_obj.get("display_name") or model_obj.get("id")
            if mname:
                line1_parts.append(f"{mname}")

    line1_parts.append(format_context_segment(payload.get("context_window"), warn_pct=warn_pct))
    lines = [SEP.join(line1_parts)]

    quota_line = format_quota_line(payload.get("quota"), term_width=term_width)
    if quota_line:
        lines.append(quota_line)

    return "\n".join(lines)


def main():
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except OSError:
            raw = ""
    payload = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
        except ValueError:
            payload = {}

    out = render(payload)
    if out:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
