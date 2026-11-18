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
        self.assertEqual(statusline.format_dir(r"D:\\"), "D:/")
        self.assertEqual(statusline.format_dir(r"D:\work\boyue"), "D:/work/boyue")
        self.assertEqual(statusline.format_dir(r"D:\work\company\boyue\app"), "D:/…/boyue/app")

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
        out = strip_ansi(statusline.render(payload))
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
        out = strip_ansi(statusline.render(payload))
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
        out = strip_ansi(statusline.render(payload))
        self.assertIn("上下文 [██░░░] 40% (419k/1M)", out)
        self.assertIn("Gemini 5h 50%(1h)", out)
        self.assertNotIn("Gemini 5h [", out)

        ultra_narrow = dict(payload, terminal_width=68)
        out_ultra = strip_ansi(statusline.render(ultra_narrow))
        self.assertIn("上下文 [██░░░] 40%", out_ultra)
        self.assertNotIn("(419k/1M)", out_ultra)

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

            install.install(agy_dir=tmp_agy, stack_with_default=True)
            self.assertTrue(os.path.isfile(os.path.join(tmp_agy, "statusline.py")))
            self.assertTrue(os.path.isfile(settings_path + ".bak"))

            with open(settings_path, "r", encoding="utf-8") as f:
                merged = json.load(f)
            self.assertEqual(merged["model"], "Gemini 4 Carbon (High)")
            self.assertEqual(merged["trustedWorkspaces"], ["/Users/example/中文目录"])
            self.assertTrue(merged["statusLine"]["enabled"])
            self.assertTrue(merged["statusLine"]["stack_with_default"])
            if os.name == "nt":
                self.assertNotIn('"', merged["statusLine"]["command"])

            install.uninstall(agy_dir=tmp_agy)
            with open(settings_path, "r", encoding="utf-8") as f:
                restored = json.load(f)
            self.assertNotIn("statusLine", restored)
            self.assertEqual(restored["model"], "Gemini 4 Carbon (High)")
            self.assertFalse(os.path.exists(os.path.join(tmp_agy, "statusline.py")))

    def test_install_works_in_directory_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            spaced_agy = os.path.join(tmp_root, "dir with spaces", "antigravity-cli")
            install.install(agy_dir=spaced_agy, stack_with_default=True)
            with open(os.path.join(spaced_agy, "settings.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cmd = cfg["statusLine"]["command"]
            if os.name == "nt":
                self.assertNotIn('"', cmd)
            out = install.verify_script(os.path.join(spaced_agy, "statusline.py"), command=cmd)
            self.assertIn("上下文", strip_ansi(out))

    def test_replace_default_enables_show_model_automatically(self):
        with tempfile.TemporaryDirectory() as tmp_agy:
            install.main(["--agy-dir", tmp_agy, "--replace-default"])
            with open(os.path.join(tmp_agy, "settings.json"), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertFalse(cfg["statusLine"]["stack_with_default"])
            self.assertIn("--show-model", cfg["statusLine"]["command"])

    def test_windows_fallback_when_short_path_unavailable(self):
        if os.name != "nt":
            return
        with tempfile.TemporaryDirectory() as tmp_root:
            spaced_dir = os.path.join(tmp_root, "no 8dot3 fallback")
            os.makedirs(spaced_dir, exist_ok=True)
            target = os.path.join(spaced_dir, "statusline.py")
            with open(os.path.join(REPO_ROOT, "statusline.py"), "rb") as src, open(target, "wb") as dst:
                dst.write(src.read())

            orig_short = install._win_short_path
            try:
                install._win_short_path = lambda p: p
                cmd = install.format_statusline_command(target)
                self.assertNotIn('"', cmd)
                out = install.verify_script(target, command=cmd)
                self.assertIn("上下文", strip_ansi(out))
            finally:
                install._win_short_path = orig_short


if __name__ == "__main__":
    unittest.main()
