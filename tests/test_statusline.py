import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import install  # noqa: E402
import statusline  # noqa: E402

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(s):
    return ANSI_RE.sub("", s)


class StatuslineTests(unittest.TestCase):
    def test_format_dir_variants(self):
        home = os.path.expanduser("~")
        self.assertEqual(statusline.format_dir(home), "~")
        self.assertEqual(
            statusline.format_dir(os.path.join(home, "Projects", "agy-statusline")),
            "~/Projects/agy-statusline",
        )
        self.assertEqual(
            statusline.format_dir(os.path.join(home, "Documents", "卜悦", "boyue-finance")),
            "~/…/卜悦/boyue-finance",
        )
        self.assertEqual(
            statusline.format_dir(os.path.join(home, "Documents", "deep", "app"), ascii_mode=True),
            "~/.../deep/app",
        )
        self.assertEqual(statusline.format_dir(r"D:\\"), "D:/")
        self.assertEqual(statusline.format_dir(r"D:\work\boyue"), "D:/work/boyue")
        self.assertEqual(statusline.format_dir(r"D:\work\company\boyue\app"), "D:/…/boyue/app")
        self.assertEqual(
            statusline.format_dir(r"D:\work\company\boyue\app", ascii_mode=True),
            "D:/.../boyue/app",
        )

    def test_render_full_payload_and_quotas(self):
        payload = {
            "workspace": {"current_dir": os.path.expanduser("~/Projects/agy-statusline")},
            "model": {"display_name": "Gemini 4 Carbon (High)"},
            "context_window": {
                "used_percentage": 18.4,
                "context_window_size": 1048576,
                "current_usage": {
                    "input_tokens": 12000,
                    "output_tokens": 800,
                    "cache_read_input_tokens": 180000,
                },
            },
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.87, "reset_in_seconds": 7860},
                "gemini-weekly": {"remaining_fraction": 0.74, "reset_in_seconds": 356400},
                "gemini-argon-wtu-weekly": {"remaining_fraction": 0.08, "reset_in_seconds": 566564},
                "3p-5h": {"remaining_fraction": 1.0, "reset_in_seconds": 17000, "disabled": True},
                "3p-weekly": {"remaining_fraction": 0.92, "reset_in_seconds": 330852},
            },
            "terminal_width": 140,
        }
        out = strip_ansi(statusline.render(payload, lang="zh-CN", ascii_mode=False))
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("~/Projects/agy-statusline", lines[0])
        self.assertIn("上下文 [██░░░░░░░░] 18% (193k/1M)", lines[0])
        self.assertNotIn("建议交接", lines[0])

        self.assertIn("Gemini 5h [████░] 87%(2h11m)", lines[1])
        self.assertIn("周 [████░] 74%(4d3h)", lines[1])
        self.assertIn("Argon周 [░░░░░] 8%", lines[1])
        # disabled 3p-5h must be omitted, while active 3p-weekly is shown
        self.assertNotIn("Claude/GPT 5h", lines[1])
        self.assertIn("Claude/GPT 周 [█████] 92%", lines[1])

    def test_context_85_percent_handoff_alert(self):
        payload = {
            "cwd": os.path.expanduser("~/Documents/卜悦/boyue-finance"),
            "context_window": {
                "used_percentage": 86.2,
                "context_window_size": 1048576,
                "current_usage": {"input_tokens": 904000},
            },
        }
        out = strip_ansi(statusline.render(payload, lang="zh-CN", ascii_mode=False))
        self.assertIn("~/…/卜悦/boyue-finance", out)
        self.assertIn("86%", out)
        self.assertIn("⚠建议交接", out)

    def test_narrow_terminal_hides_quota_bars(self):
        payload = {
            "cwd": os.path.expanduser("~"),
            "context_window": {
                "used_percentage": 40.0,
                "context_window_size": 1048576,
                "current_usage": {"input_tokens": 419430},
            },
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.5, "reset_in_seconds": 3600},
            },
            "terminal_width": 80,
        }
        out = strip_ansi(statusline.render(payload, lang="zh-CN", ascii_mode=False))
        self.assertIn("上下文 [██░░░] 40% (419k/1M)", out)
        self.assertIn("Gemini 5h 50%(1h)", out)
        self.assertNotIn("Gemini 5h [", out)

        ultra_narrow = dict(payload, terminal_width=68)
        out_ultra = strip_ansi(statusline.render(ultra_narrow, lang="zh-CN", ascii_mode=False))
        self.assertIn("上下文 [██░░░] 40%", out_ultra)
        self.assertNotIn("(419k/1M)", out_ultra)

    def test_cmux_four_quotas_progressive_width_adaptation(self):
        # Exact 4-bucket payload from real cmux split-pane usage
        payload = {
            "cwd": os.path.expanduser("~"),
            "context_window": {
                "used_percentage": 7.0,
                "context_window_size": 1048576,
                "current_usage": {"input_tokens": 74000},
            },
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.37, "reset_in_seconds": 720},
                "gemini-weekly": {"remaining_fraction": 0.78, "reset_in_seconds": 568800},
                "3p-5h": {"remaining_fraction": 1.0, "reset_in_seconds": 17760},
                "3p-weekly": {"remaining_fraction": 1.0, "reset_in_seconds": 568800},
            },
        }
        # 1. Wide pane (130 cols): full 5-cell bars, single quota line, fits within width
        wide = statusline.render(dict(payload, terminal_width=130), lang="zh-CN", ascii_mode=False).splitlines()
        self.assertEqual(len(wide), 2)
        self.assertIn("[██░░░] 37%(12m)", strip_ansi(wide[1]))
        self.assertTrue(strip_ansi(wide[1]).endswith("100%(6d14h)"))
        self.assertLessEqual(statusline.display_width(wide[1]), 128)

        # 2. Medium cmux pane (112 cols): auto-shrinks to 3-cell bars so 100%(6d14h) is never clipped
        medium = statusline.render(dict(payload, terminal_width=112), lang="zh-CN", ascii_mode=False).splitlines()
        self.assertEqual(len(medium), 2)
        self.assertIn("[█░░] 37%(12m)", strip_ansi(medium[1]))
        self.assertTrue(strip_ansi(medium[1]).endswith("100%(6d14h)"))
        self.assertLessEqual(statusline.display_width(medium[1]), 110)

        # 3. Compact pane (96 cols): drops mini-bars, keeps all % and countdowns on one line
        compact = statusline.render(dict(payload, terminal_width=96), lang="zh-CN", ascii_mode=False).splitlines()
        self.assertEqual(len(compact), 2)
        self.assertNotIn("Gemini 5h [", strip_ansi(compact[1]))
        self.assertTrue(strip_ansi(compact[1]).endswith("100%(6d14h)"))
        self.assertLessEqual(statusline.display_width(compact[1]), 94)

        # 4. Narrow side-by-side cmux split (76 cols): stacks Gemini and Claude/GPT onto separate lines
        narrow = statusline.render(dict(payload, terminal_width=76), lang="zh-CN", ascii_mode=False).splitlines()
        self.assertEqual(len(narrow), 3)
        self.assertIn("Gemini 5h 37%(12m)", strip_ansi(narrow[1]))
        self.assertIn("Claude/GPT 5h 100%(4h56m)", strip_ansi(narrow[2]))
        self.assertTrue(strip_ansi(narrow[2]).endswith("100%(6d14h)"))
        for ln in narrow:
            self.assertLessEqual(statusline.display_width(ln), 74)

    def test_detect_terminal_width_priority(self):
        self.assertEqual(
            statusline.detect_terminal_width(
                {"terminal_width": 108},
                env={"AGY_STATUSLINE_WIDTH": "90", "COLUMNS": "80"},
                use_tty=False,
            ),
            108,
        )
        self.assertEqual(
            statusline.detect_terminal_width(
                {},
                env={"AGY_STATUSLINE_WIDTH": "92", "COLUMNS": "80"},
                use_tty=False,
            ),
            92,
        )
        self.assertEqual(
            statusline.detect_terminal_width({}, env={"COLUMNS": "84"}, use_tty=False),
            84,
        )
        self.assertEqual(
            statusline.detect_terminal_width({}, env={}, use_tty=False, fallback=120),
            120,
        )

    def test_all_five_languages_render_labels_and_handoff(self):
        payload = {
            "cwd": os.path.expanduser("~"),
            "context_window": {
                "used_percentage": 88.0,
                "context_window_size": 1000000,
                "current_usage": {"input_tokens": 880000},
            },
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.80, "reset_in_seconds": 3600},
                "gemini-weekly": {"remaining_fraction": 0.70, "reset_in_seconds": 86400},
                "gemini-argon-wtu-weekly": {"remaining_fraction": 0.60, "reset_in_seconds": 86400},
                "3p-weekly": {"remaining_fraction": 0.90, "reset_in_seconds": 86400},
            },
            "terminal_width": 140,
        }
        expectations = {
            "en": ("Context [█████████░] 88%", "⚠handoff", "Quota  ", "wk [", "Argon wk [", "Claude/GPT wk ["),
            "zh-CN": ("上下文 [█████████░] 88%", "⚠建议交接", "配额  ", "周 [", "Argon周 [", "Claude/GPT 周 ["),
            "zh-TW": ("上下文 [█████████░] 88%", "⚠建議交接", "配額  ", "週 [", "Argon週 [", "Claude/GPT 週 ["),
            "ja": ("コンテキスト [█████████░] 88%", "⚠引継ぎ推奨", "クォータ  ", "週 [", "Argon週 [", "Claude/GPT 週 ["),
            "ko": ("컨텍스트 [█████████░] 88%", "⚠인계 권장", "할당량  ", "주간 [", "Argon주간 [", "Claude/GPT 주간 ["),
        }
        for lang, (ctx_lbl, alert_lbl, quota_lbl, wk_lbl, argon_lbl, tp_lbl) in expectations.items():
            with self.subTest(lang=lang):
                lines = strip_ansi(statusline.render(payload, lang=lang, ascii_mode=False)).splitlines()
                self.assertEqual(len(lines), 2)
                self.assertIn(ctx_lbl, lines[0])
                self.assertIn(alert_lbl, lines[0])
                self.assertTrue(lines[1].startswith(quota_lbl), lines[1])
                self.assertIn(wk_lbl, lines[1])
                self.assertIn(argon_lbl, lines[1])
                self.assertIn(tp_lbl, lines[1])

    def test_detect_lang_priority_and_unknown_locale_fallback(self):
        # 1. --lang beats AGY_STATUSLINE_LANG and LC_ALL/LANG
        self.assertEqual(
            statusline.detect_lang(
                argv=["--lang", "ja"],
                env={"AGY_STATUSLINE_LANG": "zh-CN", "LC_ALL": "ko_KR.UTF-8"},
            ),
            "ja",
        )
        self.assertEqual(
            statusline.detect_lang(
                argv=["--lang=ko"],
                env={"AGY_STATUSLINE_LANG": "zh-TW", "LANG": "en_US.UTF-8"},
            ),
            "ko",
        )
        # --lang auto defers to AGY_STATUSLINE_LANG
        self.assertEqual(
            statusline.detect_lang(
                argv=["--lang", "auto"],
                env={"AGY_STATUSLINE_LANG": "zh-TW", "LC_ALL": "en_US.UTF-8"},
            ),
            "zh-TW",
        )
        # 2. AGY_STATUSLINE_LANG beats LC_ALL / LANG
        self.assertEqual(
            statusline.detect_lang(
                argv=[],
                env={"AGY_STATUSLINE_LANG": "zh-CN", "LC_ALL": "ja_JP.UTF-8", "LANG": "en_US.UTF-8"},
            ),
            "zh-CN",
        )
        # AGY_STATUSLINE_LANG=auto defers to LC_ALL > LC_MESSAGES > LANGUAGE > LANG
        self.assertEqual(
            statusline.detect_lang(
                argv=[],
                env={"AGY_STATUSLINE_LANG": "auto", "LC_ALL": "ja_JP.UTF-8", "LANG": "ko_KR.UTF-8"},
            ),
            "ja",
        )
        self.assertEqual(
            statusline.detect_lang(
                argv=[],
                env={"LC_MESSAGES": "ko_KR.UTF-8", "LANGUAGE": "ja:en", "LANG": "zh_CN.UTF-8"},
            ),
            "ko",
        )
        self.assertEqual(
            statusline.detect_lang(
                argv=[],
                env={"LANGUAGE": ":zh_TW:ja", "LANG": "en_US.UTF-8"},
            ),
            "zh-TW",
        )
        # 3. Unknown explicit locales fall back cleanly to "en"
        for unknown in ("fr_FR.UTF-8", "de_DE", "pt_BR", "es_ES@euro", "ru_RU.UTF-8"):
            with self.subTest(locale=unknown):
                self.assertEqual(statusline.detect_lang(argv=[], env={"LANG": unknown}), "en")
        self.assertEqual(statusline.detect_lang(argv=["--lang", "fr"], env={"LANG": "zh_CN.UTF-8"}), "en")

        # 4. Neutral locales return None in normalize_lang and fall back to "en" in isolated env
        for neutral in ("", "C", "C.UTF-8", "POSIX", "auto"):
            self.assertIsNone(statusline.normalize_lang(neutral))
        self.assertEqual(statusline.detect_lang(argv=[], env={}), "en")
        self.assertEqual(statusline.detect_lang(argv=[], env={"LANG": "C.UTF-8"}), "en")

    def test_chinese_traditional_and_simplified_locale_variants(self):
        for trad in ("zh_TW.UTF-8", "zh_HK.UTF-8", "zh_MO", "zh-Hant", "zh-Hant-HK", "zh-TW", "cht"):
            with self.subTest(trad=trad):
                self.assertEqual(statusline.normalize_lang(trad), "zh-TW")
                self.assertEqual(statusline.detect_lang(argv=[], env={"LANG": trad}), "zh-TW")

        for simp in ("zh", "zh_CN.UTF-8", "zh_SG", "zh-SG.UTF-8", "zh-Hans", "zh-Hans-CN", "zh-CN", "chs"):
            with self.subTest(simp=simp):
                self.assertEqual(statusline.normalize_lang(simp), "zh-CN")
                self.assertEqual(statusline.detect_lang(argv=[], env={"LANG": simp}), "zh-CN")

        self.assertEqual(statusline.normalize_lang("ja_JP.UTF-8"), "ja")
        self.assertEqual(statusline.normalize_lang("jp"), "ja")
        self.assertEqual(statusline.normalize_lang("ko_KR.UTF-8"), "ko")
        self.assertEqual(statusline.normalize_lang("kr"), "ko")

    def test_ascii_mode_detection_and_pure_ascii_output(self):
        self.assertTrue(statusline.is_ascii_mode(argv=["--ascii"], env={}))
        self.assertTrue(statusline.is_ascii_mode(argv=[], env={"AGY_STATUSLINE_ASCII": "1"}))
        self.assertTrue(statusline.is_ascii_mode(argv=[], env={"TERM": "dumb"}))
        self.assertFalse(statusline.is_ascii_mode(argv=[], env={"TERM": "xterm-256color"}))

        # Use a non-existent ASCII path under ~ so vcs_payload branch fallback is exercised cleanly
        ascii_dir = os.path.join(os.path.expanduser("~"), "nonexistent_dir_1", "deep_dir_2", "app")
        # If ~ itself contains non-ASCII characters on a host, format_dir replaces ~ prefix with "~"
        payload = {
            "workspace": {"current_dir": ascii_dir},
            "vcs": {"branch": "main", "dirty": True},
            "context_window": {
                "used_percentage": 88.0,
                "context_window_size": 1048576,
                "current_usage": {"input_tokens": 922746},
            },
            "quota": {
                "gemini-5h": {"remaining_fraction": 0.80, "reset_in_seconds": 3600},
                "gemini-weekly": {"remaining_fraction": 0.60, "reset_in_seconds": 86400},
                "3p-weekly": {"remaining_fraction": 1.0, "reset_in_seconds": 172800},
            },
            "terminal_width": 140,
        }
        raw_out = statusline.render(payload, lang="en", ascii_mode=True)
        self.assertTrue(
            all(ord(c) < 128 for c in raw_out),
            f"Expected pure 7-bit ASCII output, got: {raw_out!r}",
        )
        clean = strip_ansi(raw_out)
        self.assertIn("~/.../deep_dir_2/app", clean)
        self.assertIn(" | git:main* | ", clean)
        self.assertIn("Context [#########-] 88%", clean)
        self.assertIn("!handoff", clean)
        self.assertIn("Quota  Gemini 5h [####-] 80%(1h) / wk [###--] 60%(1d) | Claude/GPT wk [#####] 100%(2d)", clean)

    def test_git_branch_and_dirty_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "feat/hud"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True)

            # Unborn branch before first commit
            seg_unborn = strip_ansi(statusline.get_git_segment(tmp, None))
            self.assertIn("⎇ feat/hud", seg_unborn)

            sample = os.path.join(tmp, "hello.txt")
            with open(sample, "w", encoding="utf-8") as f:
                f.write("hi\n")
            seg_untracked = strip_ansi(statusline.get_git_segment(tmp, None))
            self.assertIn("⎇ feat/hud?", seg_untracked)

            subprocess.run(["git", "add", "hello.txt"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmp, check=True, capture_output=True)
            seg_clean = strip_ansi(statusline.get_git_segment(tmp, None))
            self.assertEqual(seg_clean, "⎇ feat/hud")

            with open(sample, "a", encoding="utf-8") as f:
                f.write("dirty\n")
            seg_dirty = strip_ansi(statusline.get_git_segment(tmp, None))
            self.assertEqual(seg_dirty, "⎇ feat/hud*")
            seg_dirty_ascii = strip_ansi(statusline.get_git_segment(tmp, None, ascii_mode=True))
            self.assertEqual(seg_dirty_ascii, "git:feat/hud*")

    def test_install_preserves_existing_settings_and_uninstalls(self):
        with tempfile.TemporaryDirectory() as tmp_agy:
            settings_path = os.path.join(tmp_agy, "settings.json")
            original = {
                "model": "Gemini 4 Carbon (High)",
                "toolPermission": "always-proceed",
                "trustedWorkspaces": ["/Users/example/中文目录"],
            }
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(original, f, ensure_ascii=False)

            with contextlib.redirect_stdout(io.StringIO()):
                install.install(agy_dir=tmp_agy, stack_with_default=True)
            self.assertTrue(os.path.isfile(os.path.join(tmp_agy, "statusline.py")))
            self.assertTrue(os.path.isfile(settings_path + ".bak"))
            if os.name == "nt":
                self.assertTrue(os.path.isfile(os.path.join(tmp_agy, "statusline.cmd")))

            with open(settings_path, "r", encoding="utf-8") as f:
                merged = json.load(f)
            self.assertEqual(merged["model"], "Gemini 4 Carbon (High)")
            self.assertEqual(merged["trustedWorkspaces"], ["/Users/example/中文目录"])
            self.assertTrue(merged["statusLine"]["enabled"])
            self.assertTrue(merged["statusLine"]["stack_with_default"])
            if os.name == "nt":
                self.assertNotIn('"', merged["statusLine"]["command"])

            with contextlib.redirect_stdout(io.StringIO()):
                install.uninstall(agy_dir=tmp_agy)
            with open(settings_path, "r", encoding="utf-8") as f:
                restored = json.load(f)
            self.assertNotIn("statusLine", restored)
            self.assertEqual(restored["model"], "Gemini 4 Carbon (High)")
            self.assertFalse(os.path.exists(os.path.join(tmp_agy, "statusline.py")))
            if os.name == "nt":
                self.assertFalse(os.path.exists(os.path.join(tmp_agy, "statusline.cmd")))

    def test_install_works_in_directory_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            spaced_agy = os.path.join(tmp_root, "dir with spaces", "antigravity-cli")
            with contextlib.redirect_stdout(io.StringIO()):
                install.install(agy_dir=spaced_agy, stack_with_default=True)
            with open(os.path.join(spaced_agy, "settings.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cmd = cfg["statusLine"]["command"]
            if os.name == "nt":
                self.assertNotIn('"', cmd)
            out = strip_ansi(install.verify_script(os.path.join(spaced_agy, "statusline.py"), command=cmd))
            self.assertIn("12%", out)
            self.assertIn("Gemini 5h", out)

    def test_replace_default_enables_show_model_automatically(self):
        with tempfile.TemporaryDirectory() as tmp_agy:
            with contextlib.redirect_stdout(io.StringIO()):
                install.main(["--agy-dir", tmp_agy, "--replace-default"])
            with open(os.path.join(tmp_agy, "settings.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertFalse(cfg["statusLine"]["stack_with_default"])
            self.assertIn("--show-model", cfg["statusLine"]["command"])

    def test_install_lang_and_ascii_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp_agy:
            with contextlib.redirect_stdout(io.StringIO()):
                install.main(["--agy-dir", tmp_agy, "--lang", "ja", "--ascii"])
            with open(os.path.join(tmp_agy, "settings.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cmd = cfg["statusLine"]["command"]
            self.assertIn("--lang ja", cmd)
            self.assertIn("--ascii", cmd)
            if os.name == "nt":
                self.assertNotIn('"', cmd)

            out_ja = strip_ansi(install.verify_script(os.path.join(tmp_agy, "statusline.py"), command=cmd))
            self.assertIn("コンテキスト [#---------] 12%", out_ja)
            self.assertIn("クォータ  Gemini 5h [####-] 88%(2h) / 週 [####-] 75%(4d)", out_ja)
            self.assertNotIn("█", out_ja)
            self.assertNotIn("│", out_ja)

            # Verify --lang auto omits --lang flag while aliases normalize cleanly
            script_path = os.path.join(tmp_agy, "statusline.py")
            cmd_auto = install.format_statusline_command(script_path, lang="auto")
            self.assertNotIn("--lang", cmd_auto)
            self.assertIn("--lang zh-CN", install.format_statusline_command(script_path, lang="zh"))
            self.assertIn("--lang zh-TW", install.format_statusline_command(script_path, lang="zh_HK"))
            self.assertIn("--lang ko", install.format_statusline_command(script_path, lang="kr"))

            # Verify end-to-end subprocess output for all 5 languages + English ASCII
            expected_words = {
                "en": ("Context", "Quota"),
                "zh-CN": ("上下文", "配额"),
                "zh-TW": ("上下文", "配額"),
                "ja": ("コンテキスト", "クォータ"),
                "ko": ("컨텍스트", "할당량"),
            }
            for lang_code, (ctx_word, quota_word) in expected_words.items():
                with self.subTest(install_lang=lang_code):
                    lang_cmd = install.format_statusline_command(script_path, lang=lang_code)
                    rendered = strip_ansi(install.verify_script(script_path, command=lang_cmd))
                    self.assertIn(ctx_word, rendered)
                    self.assertIn(quota_word, rendered)

            en_ascii_proc = subprocess.run(
                [sys.executable, script_path, "--lang", "en", "--ascii"],
                input=json.dumps(
                    {
                        "workspace": {"current_dir": os.path.expanduser("~")},
                        "context_window": {"used_percentage": 90.0, "context_window_size": 100000},
                        "quota": {"gemini-weekly": {"remaining_fraction": 0.5, "reset_in_seconds": 3600}},
                    }
                ),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            self.assertTrue(all(ord(c) < 128 for c in en_ascii_proc.stdout), en_ascii_proc.stdout)
            self.assertIn("!handoff", strip_ansi(en_ascii_proc.stdout))

    def test_windows_fallback_when_short_path_unavailable(self):
        if os.name != "nt":
            return
        with tempfile.TemporaryDirectory() as tmp_root:
            spaced_dir = os.path.join(tmp_root, "no 8dot3 fallback")
            os.makedirs(spaced_dir, exist_ok=True)
            target = os.path.join(spaced_dir, "statusline.py")
            with open(os.path.join(REPO_ROOT, "statusline.py"), "rb") as src, open(target, "wb") as dst:
                dst.write(src.read())

            hostile_env = dict(
                os.environ,
                PATH=r"C:\Windows\System32;C:\Bad\A&B;C:\Bad\C|D;" + os.environ.get("PATH", ""),
            )
            orig_short = install._win_short_path
            try:
                install._win_short_path = lambda p: p
                cmd = install.format_statusline_command(target, lang="zh-CN")
                self.assertNotIn('"', cmd)
                self.assertNotIn("set PATH=", cmd)
                out = strip_ansi(install.verify_script(target, command=cmd, env=hostile_env))
                self.assertIn("上下文", out)
                self.assertIn("12%", out)
            finally:
                install._win_short_path = orig_short

    def test_windows_launcher_hostile_path_and_special_dir_chars(self):
        if os.name != "nt":
            return
        with tempfile.TemporaryDirectory() as tmp_root:
            special_agy = os.path.join(tmp_root, "测试 (x86) & spaces", "antigravity-cli")
            orig_short = install._win_short_path
            try:
                install._win_short_path = lambda p: p
                with contextlib.redirect_stdout(io.StringIO()):
                    install.main(["--agy-dir", special_agy, "--lang", "zh-CN", "--ascii"])
            finally:
                install._win_short_path = orig_short

            launcher_path = os.path.join(special_agy, "statusline.cmd")
            self.assertTrue(os.path.isfile(launcher_path))
            with open(os.path.join(special_agy, "settings.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cmd = cfg["statusLine"]["command"]
            self.assertNotIn('"', cmd)
            self.assertNotIn("set PATH=", cmd)

            hostile_env = dict(
                os.environ,
                PATH=r"C:\Windows\System32;C:\Bad\A&B;C:\Bad\C|D;" + os.environ.get("PATH", ""),
            )
            out = strip_ansi(
                install.verify_script(os.path.join(special_agy, "statusline.py"), command=cmd, env=hostile_env)
            )
            self.assertIn("上下文", out)
            self.assertIn("配额", out)
            self.assertIn("12%", out)

    def test_windows_launcher_non_ascii_python_emits_chcp(self):
        if os.name != "nt":
            return
        with tempfile.TemporaryDirectory() as tmp_root:
            script_path = os.path.join(tmp_root, "statusline.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("# stub\n")

            orig_short = install._win_short_path
            try:
                install._win_short_path = lambda p: p
                ascii_cmd = install.write_windows_launcher(
                    script_path, py_exe=r"C:\Program Files\Python312\python.exe"
                )
                with open(ascii_cmd, "rb") as f:
                    ascii_bytes = f.read()
                self.assertFalse(ascii_bytes.startswith(b"\xef\xbb\xbf"))
                self.assertIn(b"\r\n", ascii_bytes)
                ascii_text = ascii_bytes.decode("utf-8")
                self.assertNotIn("chcp 65001", ascii_text)
                self.assertIn(r'"C:\Program Files\Python312\python.exe" "%~dp0statusline.py" %*', ascii_text)

                non_ascii_cmd = install.write_windows_launcher(
                    script_path, py_exe=r"C:\Users\测试\Python312\python.exe"
                )
                with open(non_ascii_cmd, "rb") as f:
                    non_ascii_bytes = f.read()
                self.assertFalse(non_ascii_bytes.startswith(b"\xef\xbb\xbf"))
                self.assertIn(b"\r\n", non_ascii_bytes)
                non_ascii_text = non_ascii_bytes.decode("utf-8")
                self.assertIn("chcp 65001 >nul 2>nul", non_ascii_text)
                self.assertIn(r'"C:\Users\测试\Python312\python.exe" "%~dp0statusline.py" %*', non_ascii_text)
            finally:
                install._win_short_path = orig_short


if __name__ == "__main__":
    unittest.main()
