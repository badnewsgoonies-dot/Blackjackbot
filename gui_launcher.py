"""Simple GUI launcher for GOP3 Blackjack bot tools (Windows)."""

import ctypes
import re
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from config_loader import get_external_config_path, load_config


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = get_external_config_path()


def get_bundled_config_path() -> Path:
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", ""))
        return bundle_dir / "gop3_config.py"
    return ROOT / "gop3_config.py"


def get_foreground_window_title() -> str:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def read_config_value() -> str:
    try:
        cfg = load_config()
        value = getattr(cfg, "GAME_WINDOW_TITLE", None)
        return "" if value is None else str(value)
    except Exception:
        return ""


def write_config_value(value: str, disable: bool) -> bool:
    if not CONFIG_PATH.exists():
        source = get_bundled_config_path()
        if source.exists():
            CONFIG_PATH.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            CONFIG_PATH.write_text("GAME_WINDOW_TITLE = None\n", encoding="utf-8")

    text = CONFIG_PATH.read_text(encoding="utf-8")
    if disable:
        replacement = "GAME_WINDOW_TITLE = None"
    else:
        safe = value.replace("\\", "\\\\").replace("\"", "\\\"")
        replacement = f'GAME_WINDOW_TITLE = "{safe}"'

    if re.search(r"^GAME_WINDOW_TITLE\s*=\s*.*$", text, flags=re.MULTILINE):
        new_text = re.sub(
            r"^GAME_WINDOW_TITLE\s*=\s*.*$",
            replacement,
            text,
            flags=re.MULTILINE,
        )
    else:
        new_text = text + "\n" + replacement + "\n"

    CONFIG_PATH.write_text(new_text, encoding="utf-8")
    return True


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GOP3 Bot Launcher")
        self.resizable(False, False)

        self.current_title = tk.StringVar(value="(not fetched)")
        self.config_title = tk.StringVar(value=read_config_value())
        self.disable_focus = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Foreground window:").pack(side="left")
        ttk.Label(row, textvariable=self.current_title, width=50).pack(side="left", padx=6)
        ttk.Button(row, text="Refresh", command=self._refresh_foreground).pack(side="left")

        row2 = ttk.Frame(self)
        row2.pack(fill="x", **pad)
        ttk.Label(row2, text="GAME_WINDOW_TITLE:").pack(side="left")
        ttk.Entry(row2, textvariable=self.config_title, width=42).pack(side="left", padx=6)
        ttk.Button(row2, text="Set from foreground", command=self._set_from_foreground).pack(side="left")

        row3 = ttk.Frame(self)
        row3.pack(fill="x", **pad)
        ttk.Checkbutton(row3, text="Disable focus check (set to None)", variable=self.disable_focus).pack(side="left")
        ttk.Button(row3, text="Save to config", command=self._save_config).pack(side="left", padx=10)

        row4 = ttk.Frame(self)
        row4.pack(fill="x", **pad)
        ttk.Button(row4, text="Run bot (test)", command=self._run_test).pack(side="left")
        ttk.Button(row4, text="Run bot", command=self._run_bot).pack(side="left", padx=6)
        ttk.Button(row4, text="Run calibration", command=self._run_calibration).pack(side="left", padx=6)

        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status, foreground="#444").pack(fill="x", **pad)

    def _refresh_foreground(self):
        title = get_foreground_window_title()
        self.current_title.set(title if title else "(no title detected)")

    def _set_from_foreground(self):
        title = get_foreground_window_title()
        if title:
            self.config_title.set(title)
            self.status.set("Loaded current foreground title.")
        else:
            self.status.set("No foreground title detected.")

    def _save_config(self):
        ok = write_config_value(self.config_title.get(), self.disable_focus.get())
        if ok:
            self.status.set("Saved GAME_WINDOW_TITLE to gop3_config.py")
        else:
            self.status.set("Failed to write config.")

    def _run_bot(self):
        self._spawn_bot([])

    def _run_test(self):
        self._spawn_bot(["--test"])

    def _run_calibration(self):
        script = ROOT / "calibrate_positions.py"
        if not script.exists() and getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates = [
                exe_dir / "calibrate_positions.py",
                exe_dir.parent / "calibrate_positions.py",
            ]
            for cand in candidates:
                if cand.exists():
                    script = cand
                    break
        if not script.exists():
            self.status.set("Calibration script not found. Run from repo root or copy EXE there.")
            return
        try:
            subprocess.Popen(
                ["cmd", "/k", "python", str(script.name)],
                cwd=str(script.parent),
            )
            self.status.set("Launched calibration in new console.")
        except Exception as exc:
            self.status.set(f"Failed to launch calibration: {exc}")

    def _spawn_bot(self, args):
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--bot"] + args
            else:
                cmd = [sys.executable, str(Path(__file__).resolve()), "--bot"] + args
            subprocess.Popen(cmd, cwd=str(ROOT))
            self.status.set("Launched: " + " ".join(cmd))
        except Exception as exc:
            self.status.set(f"Failed to launch: {exc}")


def run_bot_mode(args):
    import blackjack_bot

    sys.argv = ["blackjack_bot.py"] + args
    blackjack_bot.main()


if __name__ == "__main__":
    if "--bot" in sys.argv:
        idx = sys.argv.index("--bot")
        run_bot_mode(sys.argv[idx + 1 :])
    else:
        app = App()
        app.mainloop()
