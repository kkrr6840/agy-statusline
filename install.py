#!/usr/bin/env python3
"""Cross-platform installer / uninstaller for agy-statusline (macOS, Linux, Windows).

Can run directly from a cloned repo:
    python3 install.py
    python3 install.py --lang ja --ascii
    python3 install.py --uninstall

Or piped directly from GitHub on a new machine:
    curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.py | python3 -
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RAW_SCRIPT_URL = (
    os.environ.get("AGY_STATUSLINE_RAW_URL")
    or "https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/statusline.py"
)

_LOCALE_TAG_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{1,8})*$")


def get_agy_dir():
    return os.path.join(os.path.expanduser("~"), ".gemini", "antigravity-cli")


def normalize_lang_option(raw):
    """Normalize --lang CLI/API option to canonical code, or None for runtime auto-detection."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"Invalid language option: {raw!r}")
    stripped = raw.strip()
    if not stripped:
        return None
    s = stripped.split("@", 1)[0].split(".", 1)[0].strip().lower().replace("_", "-")
    if s in ("", "auto"):
        return None

    if s in ("zh-tw", "zh-hk", "zh-mo", "zh-hant", "cht", "zh-cht") or s.startswith(
        ("zh-hant-", "zh-tw-", "zh-hk-", "zh-mo-")
    ):
        return "zh-TW"
    if s in ("zh", "zh-cn", "zh-sg", "zh-hans", "chs", "zh-chs") or s.startswith("zh-"):
        return "zh-CN"
    if s in ("ja", "jp") or s.startswith("ja-"):
        return "ja"
    if s in ("ko", "kr") or s.startswith("ko-"):
        return "ko"
    if s == "en" or s.startswith("en-"):
        return "en"

    if _LOCALE_TAG_RE.match(s):
        sys.stderr.write(f"Note: language '{stripped}' is not localized; falling back to 'en'.\n")
        return "en"

    raise ValueError(
        f"Invalid --lang value {raw!r} (expected one of: en, zh-CN, zh-TW, ja, ko, auto)"
    )


def _win_short_path(path):
    """Convert a Windows path with spaces to an 8.3 short path when available."""
    if not path or " " not in path or os.name != "nt":
        return path
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(1024)
        res = ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf))
        if res and buf.value and " " not in buf.value:
            return buf.value
    except Exception:
        pass
    return path


def resolve_python_command():
    """Choose a stable Python executable path for settings.json."""
    if os.name == "nt":
        # On Windows, pin exact sys.executable to avoid Microsoft Store python3.exe stub issues.
        # Avoid double quotes: agy invokes `cmd /c <command>` via Go's exec.Command, which
        # escapes `"` into `\"` that cmd.exe passes literally to python.exe.
        exe = _win_short_path(sys.executable or "python")
        return exe

    # On macOS/Linux, prefer symlinked PATH binary (e.g. /opt/homebrew/bin/python3)
    # so Homebrew patch upgrades don't invalidate Cellar paths.
    which_py = shutil.which("python3") or sys.executable or "python3"
    return f'"{which_py}"' if " " in which_py else which_py


def format_statusline_command(script_path, py_exe=None, show_model=False, lang=None, ascii_mode=False):
    norm_lang = normalize_lang_option(lang)
    flags = []
    if show_model:
        flags.append("--show-model")
    if norm_lang:
        flags.append(f"--lang {norm_lang}")
    if ascii_mode:
        flags.append("--ascii")
    extra_flag = (" " + " ".join(flags)) if flags else ""

    if os.name == "nt":
        raw_py = _win_short_path(py_exe if py_exe is not None else (sys.executable or "python"))
        raw_script = _win_short_path(script_path)

        env_prefixes = []
        if " " in raw_py:
            py_dir, py_name = os.path.split(raw_py)
            if py_dir:
                env_prefixes.append(f"set PATH={py_dir};%PATH%")
            py_part = py_name or "python"
        else:
            py_part = raw_py

        if " " in raw_script:
            script_dir, script_name = os.path.split(raw_script)
            mod_name = os.path.splitext(script_name)[0] or "statusline"
            if script_dir:
                env_prefixes.append(f"set PYTHONPATH={script_dir}")
            cmd_core = f"{py_part} -m {mod_name}{extra_flag}"
        else:
            cmd_core = f"{py_part} {raw_script}{extra_flag}"

        return "&&".join(env_prefixes + [cmd_core])

    py_cmd = resolve_python_command() if py_exe is None else (f'"{py_exe}"' if " " in py_exe else py_exe)
    # Use ~ on POSIX so settings.json stays clean and portable across home paths
    home = os.path.expanduser("~")
    if script_path.startswith(home + os.sep):
        rel = "~/" + script_path[len(home) + 1 :].replace("\\", "/")
        if " " not in rel:
            return f"{py_cmd} {rel}{extra_flag}"
    return f'{py_cmd} "{script_path}"{extra_flag}'


def load_settings(settings_path):
    if not os.path.exists(settings_path):
        return {}
    with open(settings_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {}
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in {settings_path}")
        return data


def save_settings_atomic(settings_path, data):
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    if os.path.exists(settings_path):
        shutil.copy2(settings_path, settings_path + ".bak")
    tmp_path = settings_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, settings_path)


def obtain_statusline_source():
    # When invoked from a local checkout, read sibling statusline.py
    if "__file__" in globals():
        candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statusline.py")
        if os.path.isfile(candidate):
            with open(candidate, "rb") as f:
                return f.read(), candidate
    # Otherwise fetch from GitHub raw URL (one-liner install mode)
    with urllib.request.urlopen(RAW_SCRIPT_URL, timeout=15) as resp:
        content = resp.read()
    if b"def render(" not in content:
        raise RuntimeError(f"Downloaded content from {RAW_SCRIPT_URL} did not match statusline.py")
    return content, RAW_SCRIPT_URL


def verify_script(script_path, command=None):
    sample = json.dumps(
        {
            "workspace": {"current_dir": os.getcwd()},
            "context_window": {
                "used_percentage": 12.4,
                "context_window_size": 1048576,
                "current_usage": {"input_tokens": 130000},
            },
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.88, "reset_in_seconds": 7200},
                "gemini-weekly": {"remaining_fraction": 0.75, "reset_in_seconds": 345600},
            },
        }
    )
    if command:
        runner = ["cmd", "/c", command] if os.name == "nt" else ["sh", "-c", command]
    else:
        runner = [sys.executable, script_path]
    proc = subprocess.run(
        runner,
        input=sample,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"Smoke test failed (exit {proc.returncode}): {proc.stderr}")
    return proc.stdout.strip()


def install(agy_dir=None, stack_with_default=True, show_model=None, lang=None, ascii_mode=False):
    agy_dir = agy_dir or get_agy_dir()
    os.makedirs(agy_dir, exist_ok=True)
    target_script = os.path.join(agy_dir, "statusline.py")
    settings_path = os.path.join(agy_dir, "settings.json")

    if show_model is None:
        show_model = not stack_with_default

    norm_lang = normalize_lang_option(lang)

    script_bytes, source_desc = obtain_statusline_source()
    with open(target_script, "wb") as f:
        f.write(script_bytes)
    if os.name != "nt":
        os.chmod(target_script, 0o755)

    command = format_statusline_command(
        target_script,
        show_model=bool(show_model),
        lang=norm_lang,
        ascii_mode=bool(ascii_mode),
    )
    preview = verify_script(target_script, command=command)

    settings = load_settings(settings_path)
    settings["statusLine"] = {
        "type": "command",
        "command": command,
        "padding": 0,
        "enabled": True,
        "stack_with_default": bool(stack_with_default),
    }
    save_settings_atomic(settings_path, settings)

    print(f"✓ Installed statusline script from {source_desc}")
    print(f"  Script:   {target_script}")
    print(f"  Settings: {settings_path} (backup at {settings_path}.bak)")
    print(f"  Command:  {settings['statusLine']['command']}")
    print("\nPreview:")
    print(preview)


def uninstall(agy_dir=None):
    agy_dir = agy_dir or get_agy_dir()
    target_script = os.path.join(agy_dir, "statusline.py")
    settings_path = os.path.join(agy_dir, "settings.json")

    if os.path.exists(settings_path):
        settings = load_settings(settings_path)
        if "statusLine" in settings:
            del settings["statusLine"]
            save_settings_atomic(settings_path, settings)
            print(f"✓ Removed statusLine from {settings_path}")
    if os.path.exists(target_script):
        os.remove(target_script)
        print(f"✓ Removed {target_script}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install or uninstall agy-statusline.")
    parser.add_argument("--uninstall", action="store_true", help="Remove statusLine config and script")
    parser.add_argument(
        "--replace-default",
        action="store_true",
        help="Replace agy's built-in status line instead of stacking below it (enables --show-model by default)",
    )
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument(
        "--show-model",
        dest="show_model",
        action="store_true",
        default=None,
        help="Always include active model name on line 1",
    )
    model_group.add_argument(
        "--no-show-model",
        dest="show_model",
        action="store_false",
        help="Hide model name even when --replace-default is set",
    )
    parser.add_argument(
        "--lang",
        default=None,
        help="Pin HUD language (en, zh-CN, zh-TW, ja, ko, or auto)",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="Use pure ASCII symbols instead of Unicode glyphs",
    )
    parser.add_argument("--agy-dir", default=None, help="Override ~/.gemini/antigravity-cli directory")
    args = parser.parse_args(argv)

    try:
        norm_lang = normalize_lang_option(args.lang)
    except ValueError as exc:
        parser.error(str(exc))
        return

    if args.uninstall:
        uninstall(agy_dir=args.agy_dir)
    else:
        install(
            agy_dir=args.agy_dir,
            stack_with_default=not args.replace_default,
            show_model=args.show_model,
            lang=norm_lang,
            ascii_mode=args.ascii,
        )


if __name__ == "__main__":
    main()
