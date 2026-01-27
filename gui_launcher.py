"""Simple GUI launcher for GOP3 Blackjack bot tools (Windows)."""

import ctypes
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import importlib.util

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


def load_config_from_path(path: Path):
    """Load a fresh config module from disk (avoids cached load_config())."""
    spec = importlib.util.spec_from_file_location("gop3_config_live", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load config spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_config_value() -> str:
    try:
        cfg = load_config()
        value = getattr(cfg, "GAME_WINDOW_TITLE", None)
        return "" if value is None else str(value)
    except Exception:
        return ""

def write_config_value(value: str) -> bool:
    if not CONFIG_PATH.exists():
        source = get_bundled_config_path()
        if source.exists():
            CONFIG_PATH.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            CONFIG_PATH.write_text("GAME_WINDOW_TITLE = None\n", encoding="utf-8")

    text = CONFIG_PATH.read_text(encoding="utf-8")
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


def _python_executable() -> str:
    if not getattr(sys, "frozen", False):
        exe = sys.executable
        # If the GUI is launched via pythonw.exe, spawning scripts with CREATE_NEW_CONSOLE
        # will not show a console. Prefer python.exe when available.
        try:
            if exe.lower().endswith("pythonw.exe"):
                cand = str(Path(exe).with_name("python.exe"))
                if Path(cand).exists():
                    return cand
        except Exception:
            pass
        return exe
    return os.environ.get("PYTHON", "python")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GOP3 Bot Launcher")
        self.resizable(False, False)

        self.config_title = tk.StringVar(value=read_config_value())

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        row2 = ttk.Frame(self)
        row2.pack(fill="x", **pad)
        ttk.Label(row2, text="GAME_WINDOW_TITLE:").pack(side="left")
        ttk.Entry(row2, textvariable=self.config_title, width=42).pack(side="left", padx=6)
        ttk.Button(row2, text="Set from foreground", command=self._set_from_foreground).pack(side="left")
        ttk.Button(row2, text="Save to config", command=self._save_config).pack(side="left", padx=6)

        row4 = ttk.Frame(self)
        row4.pack(fill="x", **pad)
        ttk.Button(row4, text="Run bot (test)", command=self._run_test).pack(side="left")
        ttk.Button(row4, text="Run bot", command=self._run_bot).pack(side="left", padx=6)
        ttk.Button(row4, text="Run calibration", command=self._run_calibration).pack(side="left", padx=6)
        ttk.Button(row4, text="Open debugger", command=self._open_debugger).pack(side="left", padx=6)

        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status, foreground="#444").pack(fill="x", **pad)

    def _set_from_foreground(self):
        # The launcher will be foreground when clicking the button, so do a delayed capture.
        self.status.set("Switch to the game window now... capturing in 2 seconds.")
        try:
            self.iconify()
        except Exception:
            pass
        self.after(2000, self._set_from_foreground_delayed)

    def _set_from_foreground_delayed(self):
        title = get_foreground_window_title()
        try:
            self.deiconify()
        except Exception:
            pass

        if title:
            self.config_title.set(title)
            self.status.set("Loaded foreground title (delayed capture).")
        else:
            self.status.set("No usable foreground title captured. Try again (alt-tab first).")

    def _save_config(self):
        ok = write_config_value(self.config_title.get())
        if ok:
            self.status.set("Saved settings to gop3_config.py")
        else:
            self.status.set("Failed to write config.")

    def _run_bot(self):
        # Default to click-to-bet each hand (avoids relying on in-game auto-bet).
        self._spawn_bot(["--click-bet"])

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
            python_exe = _python_executable()
            env = os.environ.copy()
            # Ensure calibration updates the same config file this GUI/bot will load.
            env["GOP3_CONFIG_PATH"] = str(CONFIG_PATH)
            subprocess.Popen(
                [python_exe, str(script.name)],
                cwd=str(script.parent),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                env=env,
            )
            self.status.set("Launched calibration in new console window.")
        except Exception as exc:
            self.status.set(f"Failed to launch calibration: {exc}")

    def _spawn_bot(self, args):
        try:
            env = os.environ.copy()
            # Ensure the bot reads the same config this GUI edits.
            env["GOP3_CONFIG_PATH"] = str(CONFIG_PATH)
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--bot"] + args
            else:
                cmd = [_python_executable(), str(Path(__file__).resolve()), "--bot"] + args
            subprocess.Popen(cmd, cwd=str(ROOT), env=env)
            self.status.set("Launched: " + " ".join(cmd))
        except Exception as exc:
            self.status.set(f"Failed to launch: {exc}")

    def _open_debugger(self):
        try:
            DebugWindow(self, config_path=CONFIG_PATH)
        except Exception as exc:
            self.status.set(f"Failed to open debugger: {exc}")


class DebugWindow(tk.Toplevel):
    def __init__(self, parent, *, config_path: Path):
        super().__init__(parent)
        self.title("Debugger")
        self.resizable(False, False)

        self.config_path = Path(config_path)
        self.cfg = None
        self.detector = None

        # Lazy import: allows GUI to open even if pyautogui is missing/misconfigured.
        try:
            import pyautogui  # type: ignore
        except Exception:
            pyautogui = None  # type: ignore
        self.pyautogui = pyautogui

        self.player_out = tk.StringVar(value="player: (not read yet)")
        self.dealer_out = tk.StringVar(value="dealer: (not read yet)")
        self.status = tk.StringVar(value="")

        self._build_ui()
        self._reload_config()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        row0 = ttk.Frame(self)
        row0.pack(fill="x", **pad)
        ttk.Label(row0, text=f"Config: {self.config_path}").pack(side="left")
        ttk.Button(row0, text="Reload config", command=self._reload_config).pack(side="right")

        # Mouse test controls
        box1 = ttk.LabelFrame(self, text="Mouse / Button Position Test")
        box1.pack(fill="x", **pad)

        ttk.Button(box1, text="Bet", command=lambda: self._move_to("bet")).grid(row=0, column=0, padx=6, pady=4)
        ttk.Button(box1, text="Hit", command=lambda: self._move_to("hit")).grid(row=0, column=1, padx=6, pady=4)
        ttk.Button(box1, text="Stand", command=lambda: self._move_to("stand")).grid(row=0, column=2, padx=6, pady=4)
        ttk.Button(box1, text="Double", command=lambda: self._move_to("double")).grid(row=1, column=0, padx=6, pady=4)
        ttk.Button(box1, text="Split", command=lambda: self._move_to("split")).grid(row=1, column=1, padx=6, pady=4)

        # Readouts
        box2 = ttk.LabelFrame(self, text="Live Read (From Screen)")
        box2.pack(fill="x", **pad)

        self.btn_read_player = ttk.Button(box2, text="Read player total", command=self._read_player)
        self.btn_read_player.grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(box2, textvariable=self.player_out, width=40).grid(row=0, column=1, padx=6, pady=4, sticky="w")

        self.btn_read_dealer = ttk.Button(box2, text="Read dealer total", command=self._read_dealer)
        self.btn_read_dealer.grid(row=1, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(box2, textvariable=self.dealer_out, width=40).grid(row=1, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(self, textvariable=self.status, foreground="#444").pack(fill="x", **pad)

    def _set_busy(self, busy: bool, msg: str = "") -> None:
        try:
            state = "disabled" if busy else "normal"
            if hasattr(self, "btn_read_player"):
                self.btn_read_player.configure(state=state)
            if hasattr(self, "btn_read_dealer"):
                self.btn_read_dealer.configure(state=state)
        except Exception:
            pass
        if msg:
            self.status.set(msg)

    def _reload_config(self):
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(str(self.config_path))
            self.cfg = load_config_from_path(self.config_path)
            # Important: do NOT import screen_capture/GOP3Detector here.
            # EasyOCR (torch) can take seconds to import and will freeze the UI thread.
            # We'll initialize the detector lazily when the user requests a read.
            self.detector = None
            self.status.set("Config reloaded (detector lazy-loaded on first read).")
        except Exception as exc:
            self.cfg = None
            self.detector = None
            self.status.set(f"Reload failed: {exc}")

    def _ensure_detector(self) -> bool:
        if self.detector is not None:
            return True
        if self.cfg is None:
            self.status.set("No config loaded.")
            return False
        try:
            from screen_capture import GOP3Detector
            self.detector = GOP3Detector(self.cfg)
            return True
        except Exception as exc:
            self.detector = None
            self.status.set(f"Detector init failed: {exc}")
            return False

    def _run_bg(self, fn, *, busy_msg: str):
        """Run a potentially slow function in a background thread and keep Tk responsive."""
        self._set_busy(True, busy_msg)

        def runner():
            try:
                fn()
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=runner, daemon=True).start()

    def _pos_for(self, name: str):
        if not self.cfg:
            return None
        if name == "bet":
            return getattr(self.cfg, "BET_BUTTON_POSITION", None)
        positions = getattr(self.cfg, "BUTTON_POSITIONS", {}) or {}
        return positions.get(name)

    def _move_to(self, name: str):
        if self.pyautogui is None:
            self.status.set("pyautogui not available; cannot move/click.")
            return
        pos = self._pos_for(name)
        if not pos:
            self.status.set(f"No configured position for '{name}'.")
            return
        x, y = int(pos[0]), int(pos[1])
        try:
            # Move only to avoid unintended in-game actions.
            self.pyautogui.moveTo(x, y, duration=0)
            self.status.set(f"Moved to {name}: ({x}, {y})")
        except Exception as exc:
            self.status.set(f"Move/click failed: {exc}")

    def _read_player(self):
        def task():
            if not self._ensure_detector():
                return
            try:
                screen = self.detector.capture_game()
                total, is_soft = self.detector.detect_player_total(screen)

                def apply():
                    if total is None:
                        self.player_out.set("player: None")
                    else:
                        self.player_out.set(f"player: {'soft' if is_soft else 'hard'} {total}")
                    self.status.set("Player read complete.")

                self.after(0, apply)
            except Exception as exc:
                self.after(0, lambda: self.status.set(f"Player read failed: {exc}"))

        self._run_bg(task, busy_msg="Reading player total (may take a few seconds first time)...")

    def _read_dealer(self):
        def task():
            if not self._ensure_detector():
                return
            try:
                screen = self.detector.capture_game()
                total = self.detector.detect_dealer_total(screen)

                def apply():
                    self.dealer_out.set(f"dealer: {total if total is not None else 'None'}")
                    self.status.set("Dealer read complete.")

                self.after(0, apply)
            except Exception as exc:
                self.after(0, lambda: self.status.set(f"Dealer read failed: {exc}"))

        self._run_bg(task, busy_msg="Reading dealer total (may take a few seconds first time)...")


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
