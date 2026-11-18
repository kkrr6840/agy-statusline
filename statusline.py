#!/usr/bin/env python3
"""Lightweight, zero-dependency statusLine renderer for Google Antigravity CLI (agy).

Reads session telemetry JSON from stdin (provided natively by agy) and local Git
HEAD/status, printing a compact two-line ANSI HUD:
  Line 1: Current directory | Git branch & dirty/ahead/behind | Context window bar (85% alert)
  Line 2: Quota overview (Gemini 5h/weekly, Argon weekly, Claude/GPT 5h/weekly)

Supports automatic locale detection (en, zh-CN, zh-TW, ja, ko; fallback en) and
an ASCII-safe mode (--ascii / AGY_STATUSLINE_ASCII=1 / TERM=dumb).
Zero external packages, zero network requests, zero credential access.
"""

import datetime
import json
import locale
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
ASCII_SEP = f" {DIM}|{RESET} "

MESSAGES = {
    "en": {
        "context": "Context",
        "handoff": "handoff",
        "quota": "Quota",
        "weekly": "wk",
        "argon_weekly": "Argon wk",
    },
    "zh-CN": {
        "context": "上下文",
        "handoff": "建议交接",
        "quota": "配额",
        "weekly": "周",
        "argon_weekly": "Argon周",
    },
    "zh-TW": {
        "context": "上下文",
        "handoff": "建議交接",
        "quota": "配額",
        "weekly": "週",
        "argon_weekly": "Argon週",
    },
    "ja": {
        "context": "コンテキスト",
        "handoff": "引継ぎ推奨",
        "quota": "クォータ",
        "weekly": "週",
        "argon_weekly": "Argon週",
    },
    "ko": {
        "context": "컨텍스트",
        "handoff": "인계 권장",
        "quota": "할당량",
        "weekly": "주간",
        "argon_weekly": "Argon주간",
    },
}


def normalize_lang(raw):
    """Normalize a locale/language tag to a canonical code, or None if unset/neutral."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    s = s.split("@", 1)[0].split(".", 1)[0].strip().lower().replace("_", "-")
    if s in ("", "c", "posix", "auto"):
        return None

    if (
        s in ("zh-tw", "zh-hk", "zh-mo", "zh-hant", "cht", "zh-cht")
        or s.startswith(("zh-hant-", "zh-tw-", "zh-hk-", "zh-mo-"))
        or "chinese (traditional)" in s
    ):
        return "zh-TW"
    if (
        s in ("zh", "zh-cn", "zh-sg", "zh-hans", "chs", "zh-chs")
        or s.startswith("zh")
        or "chinese" in s
    ):
        return "zh-CN"
    if s in ("ja", "jp") or s.startswith(("ja-", "japanese")):
        return "ja"
    if s in ("ko", "kr") or s.startswith(("ko-", "korean")):
        return "ko"
    if s == "en" or s.startswith(("en-", "english")):
        return "en"
    return "en"


def detect_lang(argv=None, env=None, use_os_fallback=None):
    """Detect HUD language in <1ms without spawning any subprocesses."""
    argv = sys.argv[1:] if argv is None else argv
    if use_os_fallback is None:
        use_os_fallback = env is None or env is os.environ
    env = os.environ if env is None else env

    # Step A: CLI --lang <code> or --lang=<code>
    cli_lang = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--lang" and i + 1 < len(argv):
            cli_lang = argv[i + 1]
            i += 2
            continue
        if isinstance(arg, str) and arg.startswith("--lang="):
            cli_lang = arg.split("=", 1)[1]
        i += 1
    if cli_lang is not None and cli_lang.strip().lower() not in ("", "auto"):
        return normalize_lang(cli_lang) or "en"

    # Step B: AGY_STATUSLINE_LANG environment variable
    env_lang = env.get("AGY_STATUSLINE_LANG")
    if env_lang is not None and env_lang.strip().lower() not in ("", "auto"):
        return normalize_lang(env_lang) or "en"

    # Step C: Standard POSIX locale variables
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        val = env.get(key)
        if not val:
            continue
        candidates = val.split(":") if key == "LANGUAGE" else [val]
        for item in candidates:
            item = item.strip()
            if not item:
                continue
            norm = normalize_lang(item)
            if norm:
                return norm

    # Step D: Native OS UI language fallback (Windows Win32 API / macOS plist / locale)
    if use_os_fallback:
        if os.name == "nt":
            try:
                import ctypes

                langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                if langid:
                    primary = langid & 0x3FF
                    sublang = (langid >> 10) & 0x3F
                    if primary == 0x04:
                        return "zh-TW" if sublang in (0x01, 0x03, 0x05) else "zh-CN"
                    if primary == 0x11:
                        return "ja"
                    if primary == 0x12:
                        return "ko"
                    return "en"
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                import plistlib

                pref_path = os.path.expanduser("~/Library/Preferences/.GlobalPreferences.plist")
                if os.path.isfile(pref_path):
                    with open(pref_path, "rb") as f:
                        prefs = plistlib.load(f)
                    langs = prefs.get("AppleLanguages")
                    if isinstance(langs, list) and langs and isinstance(langs[0], str):
                        return normalize_lang(langs[0]) or "en"
            except Exception:
                pass

        try:
            loc = locale.getlocale()[0]
            norm = normalize_lang(loc)
            if norm:
                return norm
        except Exception:
            pass

    # Step E: Default fallback
    return "en"


def is_ascii_mode(argv=None, env=None):
    """Check whether pure ASCII fallback glyphs should be used."""
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    if "--ascii" in argv:
        return True
    if (env.get("AGY_STATUSLINE_ASCII") or "").strip().lower() in ("1", "true", "yes"):
        return True
    if (env.get("TERM") or "").strip().lower() == "dumb":
        return True
    return False


def _get_messages(lang):
    if lang in MESSAGES:
        return MESSAGES[lang]
    norm = normalize_lang(lang) if isinstance(lang, str) else None
    return MESSAGES.get(norm or "en", MESSAGES["en"])


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


def make_bar(fraction, width=10, ascii_mode=False):
    f = max(0.0, min(1.0, float(fraction)))
    filled = int(round(f * width))
    fill_ch, empty_ch = ("#", "-") if ascii_mode else ("█", "░")
    return fill_ch * filled + empty_ch * (width - filled)


def format_dir(raw_dir, ascii_mode=False):
    if not raw_dir:
        return "~"
    ellipsis = "..." if ascii_mode else "…"
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
        return f"~/{ellipsis}/" + "/".join(parts[-2:])

    # Preserve Windows drive prefix (e.g. D:/…/proj/app instead of …/proj/app)
    slashed = raw_dir.replace("\\", "/")
    if len(slashed) >= 2 and slashed[0].isalpha() and slashed[1] == ":":
        drive = slashed[:2]
        rest_parts = [p for p in slashed[2:].split("/") if p]
        if not rest_parts:
            return f"{drive}/"
        if len(rest_parts) <= 2:
            return f"{drive}/" + "/".join(rest_parts)
        return f"{drive}/{ellipsis}/" + "/".join(rest_parts[-2:])

    parts = [p for p in norm.replace("\\", "/").split("/") if p]
    if len(parts) <= 2:
        return norm.replace("\\", "/")
    return f"{ellipsis}/" + "/".join(parts[-2:])


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


def get_git_segment(target_dir, vcs_payload, ascii_mode=False):
    branch_prefix = "git:" if ascii_mode else "⎇ "
    if not target_dir or not os.path.isdir(target_dir):
        if isinstance(vcs_payload, dict) and vcs_payload.get("branch"):
            b = vcs_payload["branch"]
            mark = "*" if vcs_payload.get("dirty") else ""
            color = YELLOW if mark else GREEN
            return f"{color}{branch_prefix}{b}{mark}{RESET}"
        return ""

    repo_root, git_dir = find_git_dir(target_dir)
    if not repo_root:
        return ""

    branch = read_head_branch(git_dir)
    dirty = False
    untracked = False
    ahead = 0
    behind = 0

    git_timeout = 0.40 if os.name == "nt" else 0.20
    extra_kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
    try:
        proc = subprocess.run(
            ["git", "-C", target_dir, "--no-optional-locks", "status", "--porcelain=v1", "-b"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=git_timeout,
            **extra_kwargs,
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
    up_glyph = "^" if ascii_mode else "↑"
    down_glyph = "v" if ascii_mode else "↓"
    sync = ""
    if ahead:
        sync += f" {up_glyph}{ahead}"
    if behind:
        sync += f" {down_glyph}{behind}"

    color = YELLOW if (dirty or untracked) else GREEN
    return f"{color}{branch_prefix}{branch}{marks}{sync}{RESET}"


def format_context_segment(cw, warn_pct=85.0, term_width=120, lang="en", ascii_mode=False):
    if not isinstance(cw, dict):
        cw = {}

    msg = _get_messages(lang)
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

    bar_width = 5 if term_width < 90 else 10
    bar = make_bar(used_pct / 100.0, width=bar_width, ascii_mode=ascii_mode)
    pct_str = f"{used_pct:.0f}%"

    detail = ""
    if term_width >= 72:
        if win_size > 0 and cur_tokens > 0:
            detail = f" {DIM}({fmt_tokens(cur_tokens)}/{fmt_tokens(win_size)}){RESET}"
        elif cur_tokens > 0:
            detail = f" {DIM}({fmt_tokens(cur_tokens)}){RESET}"

    warn_glyph = "!" if ascii_mode else "⚠"
    alert = f" {BOLD}{RED}{warn_glyph}{msg['handoff']}{RESET}" if used_pct >= warn_pct else ""
    return f"{DIM}{msg['context']}{RESET} {color}[{bar}] {pct_str}{RESET}{detail}{alert}"


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


def fmt_quota_item(label, bucket, show_bar=True, ascii_mode=False):
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

    bar_part = f"[{make_bar(rem_f, width=5, ascii_mode=ascii_mode)}] " if show_bar else ""
    dur = fmt_duration(resolve_reset_seconds(bucket))
    dur_part = f"{DIM}({dur}){RESET}" if dur else ""
    return f"{label} {color}{bar_part}{pct}%{RESET}{dur_part}"


def format_quota_line(quota, term_width=120, lang="en", ascii_mode=False):
    if not isinstance(quota, dict) or not quota:
        return ""

    msg = _get_messages(lang)
    sep = ASCII_SEP if ascii_mode else SEP
    dot_sep = f" {DIM}/{RESET} " if ascii_mode else f" {DIM}·{RESET} "
    show_bar = term_width >= 105
    groups = []

    gemini_items = []
    for key, label in (
        ("gemini-5h", "5h"),
        ("gemini-weekly", msg["weekly"]),
        ("gemini-argon-wtu-weekly", msg["argon_weekly"]),
    ):
        rendered = fmt_quota_item(label, quota.get(key), show_bar=show_bar, ascii_mode=ascii_mode)
        if rendered:
            gemini_items.append(rendered)
    if gemini_items:
        groups.append(f"{CYAN}Gemini{RESET} " + dot_sep.join(gemini_items))

    tp_items = []
    for key, label in (("3p-5h", "5h"), ("3p-weekly", msg["weekly"])):
        rendered = fmt_quota_item(label, quota.get(key), show_bar=show_bar, ascii_mode=ascii_mode)
        if rendered:
            tp_items.append(rendered)
    if tp_items:
        groups.append(f"{MAGENTA}Claude/GPT{RESET} " + dot_sep.join(tp_items))

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
        rendered = fmt_quota_item(key, quota.get(key), show_bar=False, ascii_mode=ascii_mode)
        if rendered:
            extra_items.append(rendered)
    if extra_items:
        groups.append(dot_sep.join(extra_items))

    if not groups:
        return ""
    return f"{DIM}{msg['quota']}{RESET}  " + sep.join(groups)


def render(payload, lang=None, ascii_mode=None):
    if not isinstance(payload, dict):
        payload = {}

    if lang is None or (isinstance(lang, str) and lang.strip().lower() in ("", "auto")):
        resolved_lang = detect_lang()
    else:
        resolved_lang = normalize_lang(lang) or "en"

    if ascii_mode is None:
        resolved_ascii = is_ascii_mode()
    else:
        resolved_ascii = bool(ascii_mode)

    sep = ASCII_SEP if resolved_ascii else SEP

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

    line1_parts = [f"{CYAN}{format_dir(raw_dir, ascii_mode=resolved_ascii)}{RESET}"]

    git_seg = get_git_segment(raw_dir, payload.get("vcs"), ascii_mode=resolved_ascii)
    if git_seg:
        line1_parts.append(git_seg)

    if os.environ.get("AGY_STATUSLINE_SHOW_MODEL") == "1" or "--show-model" in sys.argv[1:]:
        model_obj = payload.get("model")
        if isinstance(model_obj, dict):
            mname = model_obj.get("display_name") or model_obj.get("id")
            if mname:
                line1_parts.append(f"{mname}")

    line1_parts.append(
        format_context_segment(
            payload.get("context_window"),
            warn_pct=warn_pct,
            term_width=term_width,
            lang=resolved_lang,
            ascii_mode=resolved_ascii,
        )
    )
    lines = [sep.join(line1_parts)]

    quota_line = format_quota_line(
        payload.get("quota"),
        term_width=term_width,
        lang=resolved_lang,
        ascii_mode=resolved_ascii,
    )
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
