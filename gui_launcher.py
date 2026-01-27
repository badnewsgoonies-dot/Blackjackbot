"""Simple GUI launcher for GOP3 Blackjack bot tools (Windows)."""

import ctypes
from ctypes import wintypes
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import importlib.util
import keyboard

from config_loader import get_external_config_path, load_config
from auto_calibration import AutoCalibrator


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


def _python_executable() -> str:
    if not getattr(sys, "frozen", False):
        return sys.executable
    return os.environ.get("PYTHON", "python")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GOP3 Bot Launcher")
        self.resizable(False, False)

        self.current_title = tk.StringVar(value="(not fetched)")
        self.config_title = tk.StringVar(value=read_config_value())
        self.disable_focus = tk.BooleanVar(value=False)

        self._build_ui()
        self.overlay = None
        self.overlay_path = None
        self._start_thread = None
        self._start_event = None
        self._cancel_event = None
        self.auto_cal = AutoCalibrator(enabled=True)

    def _capture_screen_bgr(self):
        try:
            import pyautogui  # type: ignore
        except Exception:
            return None
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return None
        try:
            shot = pyautogui.screenshot()
            bgr = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
            return bgr
        except Exception:
            return None

    def _bind_start_keys(self):
        try:
            self.unbind_all("<F9>")
            self.unbind_all("<Escape>")
        except Exception:
            pass
        self._start_event = threading.Event()
        self._cancel_event = threading.Event()
        try:
            self.bind_all("<F9>", lambda _evt: self._start_event.set())
            self.bind_all("<Escape>", lambda _evt: self._cancel_event.set())
        except Exception:
            pass

    def _unbind_start_keys(self):
        try:
            self.unbind_all("<F9>")
            self.unbind_all("<Escape>")
        except Exception:
            pass
        self._start_event = None
        self._cancel_event = None

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
        ttk.Button(row4, text="Open debugger", command=self._open_debugger).pack(side="left", padx=6)
        ttk.Button(row4, text="Live reader", command=self._open_live_reader).pack(side="left", padx=6)

        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status, foreground="#444").pack(fill="x", **pad)

        # Log panel
        log_frame = ttk.LabelFrame(self, text="Bot Output")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)
        ttk.Button(self, text="Clear Log", command=self._clear_log).pack(anchor="e", padx=10, pady=2)

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
        ok = write_config_value(
            self.config_title.get(),
            self.disable_focus.get(),
        )
        if ok:
            self.status.set("Saved settings to gop3_config.py")
        else:
            self.status.set("Failed to write config.")

    def _focus_game_window(self) -> bool:
        if sys.platform != "win32":
            return False
        title = self.config_title.get()
        if not title:
            return False

        user32 = ctypes.windll.user32

        matches = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, lparam):
            buf = ctypes.create_unicode_buffer(256)
            length = user32.GetWindowTextW(hwnd, buf, 255)
            if length == 0:
                return True
            window_title = buf.value
            if title.lower() in window_title.lower():
                matches.append(hwnd)
                return False
            return True

        user32.EnumWindows(enum_proc, 0)
        if not matches:
            return False

        hwnd = matches[0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True

    def _scale_point(self, point):
        try:
            import pyautogui  # type: ignore
        except Exception:
            return point
        if not point:
            return point
        if self.auto_cal and self.auto_cal.transform:
            return self.auto_cal.apply_point(point)
        current_w, current_h = pyautogui.size()
        cfg = load_config()
        base_w = getattr(cfg, "SCREEN_WIDTH", current_w) or current_w
        base_h = getattr(cfg, "SCREEN_HEIGHT", current_h) or current_h
        sx = current_w / float(base_w)
        sy = current_h / float(base_h)
        if abs(sx - 1.0) < 0.01 and abs(sy - 1.0) < 0.01:
            return point
        return (int(round(point[0] * sx)), int(round(point[1] * sy)))

    def _region_center(self, region_name: str):
        try:
            cfg = load_config()
        except Exception:
            return None
        region = getattr(cfg, region_name, None)
        if not region:
            return None
        try:
            import pyautogui  # type: ignore
        except Exception:
            return None
        w, h = pyautogui.size()
        if self.auto_cal and self.auto_cal.transform:
            x1, y1, x2, y2 = self.auto_cal.region_rect(region, (h, w, 3))
            cx = int((x1 + x2) / 2.0)
            cy = int((y1 + y2) / 2.0)
            return (cx, cy)
        cx = int((region["x_percent"][0] + region["x_percent"][1]) / 2.0 * w)
        cy = int((region["y_percent"][0] + region["y_percent"][1]) / 2.0 * h)
        return (cx, cy)

    def _preflight_preview(self):
        try:
            import pyautogui  # type: ignore
        except Exception:
            self.status.set("Preflight skipped: pyautogui unavailable.")
            return

        screen = self._capture_screen_bgr()
        if self.auto_cal and screen is not None:
            transform = self.auto_cal.calibrate(screen)
            if transform:
                window = self.auto_cal.estimate_window_rect(screen)
                if window:
                    self.status.set(f"Auto-calibration OK (scale={transform.scale:.3f}, window={window}).")
                else:
                    self.status.set(f"Auto-calibration OK (scale={transform.scale:.3f}).")
            else:
                self.status.set("Auto-calibration unavailable; using scale-only preview.")

        # If not Windows, warn and skip focus/overlay but still preview
        positions = getattr(load_config(), "BUTTON_POSITIONS", {}) or {}
        seq = ["hit", "stand", "double", "split"]
        points = []
        for name in seq:
            if name in positions:
                points.append(self._scale_point(positions[name]))

        player_center = self._region_center("PLAYER_TOTAL_REGION")
        dealer_center = self._region_center("DEALER_TOTAL_REGION")
        for pt in (player_center, dealer_center):
            if pt:
                points.append(pt)

        if not points:
            self.status.set("Preflight skipped: no positions available.")
            return

        for pt in points:
            pyautogui.moveTo(pt[0], pt[1], duration=0.35)
            time.sleep(0.05)
        # Move to center after preview
        try:
            w, h = pyautogui.size()
            pyautogui.moveTo(w // 2, h // 2, duration=0.2)
        except Exception:
            pass

    def _can_show_overlay(self) -> bool:
        return sys.platform == "win32"

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
            hud_path = Path(tempfile.gettempdir()) / "gop3_hud_state.json"
            env["GOP3_HUD_STATE"] = "1"
            env["GOP3_HUD_PATH"] = str(hud_path)
            self.overlay_path = hud_path

            if self._focus_game_window():
                self.status.set("Brought game window to front.")
            else:
                self.status.set("Could not focus game window (continuing).")

            self._preflight_preview()
            self._bind_start_keys()
            self.status.set("Press F9 to start bot (Esc to cancel). If hotkeys fail, click this window and press F9.")

            def wait_keys():
                while True:
                    try:
                        if keyboard.is_pressed("f9"):
                            break
                    except Exception:
                        pass
                    if self._start_event and self._start_event.is_set():
                        break
                    try:
                        if keyboard.is_pressed("esc"):
                            self.after(0, lambda: self.status.set("Start canceled (Esc)."))
                            self.after(0, self._unbind_start_keys)
                            return
                    except Exception:
                        pass
                    if self._cancel_event and self._cancel_event.is_set():
                        self.after(0, lambda: self.status.set("Start canceled (Esc)."))
                        self.after(0, self._unbind_start_keys)
                        return
                    time.sleep(0.05)

                # Launch bot after F9
                self.after(0, self._unbind_start_keys)
                if getattr(sys, "frozen", False):
                    cmd = [sys.executable, "--bot"] + args
                else:
                    cmd = [sys.executable, str(Path(__file__).resolve()), "--bot"] + args
                proc = subprocess.Popen(
                    cmd, cwd=str(ROOT), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                # Stream output to log panel
                def stream_output():
                    try:
                        for line in proc.stdout:
                            self.after(0, lambda l=line: self._append_log(l))
                    except Exception:
                        pass
                threading.Thread(target=stream_output, daemon=True).start()

                if self._can_show_overlay():
                    if self.overlay:
                        try:
                            self.overlay.destroy()
                        except Exception:
                            pass
                    self.overlay = HUDOverlay(self, hud_path=hud_path, window_title=self.config_title.get())
                self.after(0, lambda: self.status.set("Launched: " + " ".join(cmd)))

            if self._start_thread and self._start_thread.is_alive():
                try:
                    self._start_thread.join(timeout=0)
                except Exception:
                    pass
            self._start_thread = threading.Thread(target=wait_keys, daemon=True)
            self._start_thread.start()
        except Exception as exc:
            self.status.set(f"Failed to launch: {exc}")

    def _open_debugger(self):
        try:
            DebugWindow(self, config_path=CONFIG_PATH)
        except Exception as exc:
            self.status.set(f"Failed to open debugger: {exc}")

    def _open_live_reader(self):
        try:
            LiveReaderWindow(self, config_path=CONFIG_PATH)
        except Exception as exc:
            self.status.set(f"Failed to open live reader: {exc}")

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _test_anchors(self):
        try:
            screen = self._capture_screen_bgr()
            if screen is None:
                self.status.set("Anchor test failed: screenshot unavailable.")
                return
            transform = self.auto_cal.calibrate(screen)
            if not transform:
                self.status.set("Anchor test failed: no matches (fallback mode).")
                return
            anchors = ", ".join(a.name for a in transform.anchors)
            # Light visual check on current frame
            try:
                from screen_capture import GOP3Detector
                detector = GOP3Detector(load_config())
                detector.auto_cal = self.auto_cal
                state = detector.detect_game_state(screen)
                buttons = state.get("buttons", {}) or {}
                required = getattr(load_config(), "REQUIRE_BUTTONS_FOR_ACTION", ("hit", "stand"))
                missing = [b for b in required if b and b not in buttons]
                visual_ok = state.get("player_total") is not None and state.get("dealer_total") is not None and not missing
                visual_text = "ok" if visual_ok else "unstable"
            except Exception:
                visual_text = "unknown"
            self.status.set(
                f"Anchor test OK (scale={transform.scale:.3f}, anchors={anchors}) | visual: {visual_text}"
            )
        except Exception as exc:
            self.status.set(f"Anchor test failed: {exc}")


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
        self._scale_warned = False

        self.player_out = tk.StringVar(value="player: (not read yet)")
        self.dealer_out = tk.StringVar(value="dealer: (not read yet)")
        self.status = tk.StringVar(value="")
        self._read_busy = False
        self._btn_read_player = None
        self._btn_read_dealer = None

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

        self.click_after_move = tk.BooleanVar(value=False)
        ttk.Checkbutton(box1, text="Click after move", variable=self.click_after_move).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=4)

        ttk.Button(box1, text="Hit", command=lambda: self._move_to("hit")).grid(row=1, column=0, padx=6, pady=4)
        ttk.Button(box1, text="Stand", command=lambda: self._move_to("stand")).grid(row=1, column=1, padx=6, pady=4)
        ttk.Button(box1, text="Double", command=lambda: self._move_to("double")).grid(row=1, column=2, padx=6, pady=4)
        ttk.Button(box1, text="Split", command=lambda: self._move_to("split")).grid(row=2, column=0, padx=6, pady=4)

        # Readouts
        box2 = ttk.LabelFrame(self, text="Live Read (From Screen)")
        box2.pack(fill="x", **pad)

        self._btn_read_player = ttk.Button(box2, text="Read player total", command=self._read_player)
        self._btn_read_player.grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(box2, textvariable=self.player_out, width=40).grid(row=0, column=1, padx=6, pady=4, sticky="w")

        self._btn_read_dealer = ttk.Button(box2, text="Read dealer total", command=self._read_dealer)
        self._btn_read_dealer.grid(row=1, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(box2, textvariable=self.dealer_out, width=40).grid(row=1, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(self, textvariable=self.status, foreground="#444").pack(fill="x", **pad)

    def _reload_config(self):
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(str(self.config_path))
            self.cfg = load_config_from_path(self.config_path)
            from screen_capture import GOP3Detector
            self.detector = GOP3Detector(self.cfg)
            self.status.set("Config reloaded.")
        except Exception as exc:
            self.cfg = None
            self.detector = None
            self.status.set(f"Reload failed: {exc}")

    def _pos_for(self, name: str):
        if not self.cfg:
            return None
        positions = getattr(self.cfg, "BUTTON_POSITIONS", {}) or {}
        base = positions.get(name)
        if base is None:
            return None
        # Apply same scaling used at runtime when resolution differs from calibration
        try:
            if self.pyautogui is None:
                return base
            current_w, current_h = self.pyautogui.size()
            base_w = getattr(self.cfg, "SCREEN_WIDTH", current_w)
            base_h = getattr(self.cfg, "SCREEN_HEIGHT", current_h)
            if not base_w or not base_h:
                return base
            scale_x = current_w / float(base_w)
            scale_y = current_h / float(base_h)
            if abs(scale_x - 1.0) < 0.01 and abs(scale_y - 1.0) < 0.01:
                return base
            if not self._scale_warned:
                self.status.set(f"Scaling buttons {base_w}x{base_h} -> {current_w}x{current_h} (sx={scale_x:.2f}, sy={scale_y:.2f})")
                self._scale_warned = True
            return (int(round(base[0] * scale_x)), int(round(base[1] * scale_y)))
        except Exception:
            return base

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
            # Move only (default). Optional click for rapid validation.
            self.pyautogui.moveTo(x, y, duration=0)
            if self.click_after_move.get():
                self.pyautogui.click(x, y)
            self.status.set(f"Moved to {name}: ({x}, {y})" + (" and clicked" if self.click_after_move.get() else ""))
        except Exception as exc:
            self.status.set(f"Move/click failed: {exc}")

    def _set_read_busy(self, busy: bool):
        self._read_busy = busy
        state = "disabled" if busy else "normal"
        if self._btn_read_player is not None:
            self._btn_read_player.configure(state=state)
        if self._btn_read_dealer is not None:
            self._btn_read_dealer.configure(state=state)

    def _read_player(self):
        if not self.detector:
            self.status.set("Detector not initialized (reload config).")
            return
        if self._read_busy:
            self.status.set("Read in progress...")
            return
        self._set_read_busy(True)
        self.status.set("Reading player total...")

        def work():
            try:
                screen = self.detector.capture_game()
                total, is_soft = self.detector.detect_player_total(screen)
                if total is None:
                    msg = "player: None"
                else:
                    msg = f"player: {'soft' if is_soft else 'hard'} {total}"
                self.after(0, lambda: self.player_out.set(msg))
                self.after(0, lambda: self.status.set("Player read complete."))
            except Exception as exc:
                self.after(0, lambda: self.status.set(f"Player read failed: {exc}"))
            finally:
                self.after(0, lambda: self._set_read_busy(False))

        threading.Thread(target=work, daemon=True).start()

    def _read_dealer(self):
        if not self.detector:
            self.status.set("Detector not initialized (reload config).")
            return
        if self._read_busy:
            self.status.set("Read in progress...")
            return
        self._set_read_busy(True)
        self.status.set("Reading dealer total...")

        def work():
            try:
                screen = self.detector.capture_game()
                total = self.detector.detect_dealer_total(screen)
                msg = f"dealer: {total if total is not None else 'None'}"
                self.after(0, lambda: self.dealer_out.set(msg))
                self.after(0, lambda: self.status.set("Dealer read complete."))
            except Exception as exc:
                self.after(0, lambda: self.status.set(f"Dealer read failed: {exc}"))
            finally:
                self.after(0, lambda: self._set_read_busy(False))

        threading.Thread(target=work, daemon=True).start()


class HUDOverlay(tk.Toplevel):
    """Small topmost header showing phase/totals/decision while bot runs."""

    def __init__(self, parent, *, hud_path: Path, window_title: str):
        super().__init__(parent)
        self.hud_path = Path(hud_path)
        self.window_title = window_title
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#111111")

        self.phase_var = tk.StringVar(value="phase: --")
        self.totals_var = tk.StringVar(value="P: --  D: --")
        self.action_var = tk.StringVar(value="action: --")
        self.cal_var = tk.StringVar(value="cal: --")
        self.visual_var = tk.StringVar(value="vis: --")
        self.last_state = None
        self.warned_stale = False

        pad = {"padx": 10, "pady": 4}
        row = ttk.Frame(self, padding="6 2 6 2")
        row.pack(fill="x")
        ttk.Label(row, textvariable=self.phase_var, width=16).pack(side="left")
        ttk.Label(row, textvariable=self.totals_var, width=22, anchor="center").pack(side="left", expand=True)
        ttk.Label(row, textvariable=self.action_var, width=28, anchor="e").pack(side="right")
        ttk.Label(row, textvariable=self.cal_var, width=12, anchor="e").pack(side="right", padx=(8, 0))
        ttk.Label(row, textvariable=self.visual_var, width=10, anchor="e").pack(side="right", padx=(8, 0))

        self.after(200, self._tick)

    def _game_rect(self):
        if sys.platform != "win32":
            return None
        if not self.window_title:
            return None
        user32 = ctypes.windll.user32
        matches = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, lparam):
            buf = ctypes.create_unicode_buffer(256)
            length = user32.GetWindowTextW(hwnd, buf, 255)
            if length == 0:
                return True
            window_title = buf.value
            if self.window_title.lower() in window_title.lower():
                matches.append(hwnd)
                return False
            return True

        user32.EnumWindows(enum_proc, 0)
        if not matches:
            return None
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(matches[0], ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)

    def _read_state(self):
        try:
            if not self.hud_path.exists():
                return None
            text = self.hud_path.read_text(encoding="utf-8")
            data = json.loads(text)
            self.last_state = data
            return data
        except Exception:
            return self.last_state

    def _tick(self):
        state = self._read_state()
        if state:
            phase = state.get("phase") or "--"
            pt = state.get("player_total")
            dt = state.get("dealer_total")
            soft = state.get("is_soft")
            action = state.get("action") or "--"
            auto_cal = state.get("auto_cal") or {}
            cal_status = auto_cal.get("status") or "--"
            cal_scale = auto_cal.get("scale")
            if cal_scale:
                cal_text = f"{cal_status}:{cal_scale:.2f}"
            else:
                cal_text = f"{cal_status}"
            visual_ok = state.get("visual_ok")
            visual_text = "ok" if visual_ok else "unstable"
            ruleset = state.get("ruleset") or "--"
            ptxt = "--" if pt is None else f"{'S' if soft else 'H'}{pt}"
            dtxt = "--" if dt is None else str(dt)
            self.phase_var.set(f"phase: {phase}")
            self.totals_var.set(f"P: {ptxt}  D: {dtxt}")
            action_text = action.upper() if isinstance(action, str) else action
            self.action_var.set(f"{ruleset} | {action_text}")
            self.cal_var.set(f"cal: {cal_text}")
            self.visual_var.set(f"vis: {visual_text}")

        rect = self._game_rect()
        if rect:
            x1, y1, x2, _ = rect
            width = max(420, min(620, x2 - x1))
            height = 28
            self.geometry(f"{width}x{height}+{x1}+{max(0, y1 - height)}")
            self.deiconify()
            if sys.platform == "win32":
                try:
                    hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                    # WS_EX_LAYERED (0x80000) | WS_EX_TRANSPARENT (0x20)
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
                    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
                except Exception:
                    if not getattr(self, "_warned_clickthrough", False):
                        print("[WARN] HUD overlay click-through not available; overlay stays topmost.")
                        if hasattr(self.master, "status"):
                            try:
                                self.master.status.set("HUD overlay not click-through; may block clicks.")
                            except Exception:
                                pass
                        self._warned_clickthrough = True
        else:
            # If no window found, keep hidden but retry.
            self.withdraw()
        # Stale warning if data older than 2s
        if self.last_state and not self.warned_stale:
            ts = self.last_state.get("ts")
            if ts and (time.time() - ts) > 2.0:
                self.status_var = getattr(self, "status_var", None)
                print("[WARN] HUD overlay: state stale (>2s).")
                self.warned_stale = True

        self.after(300, self._tick)


class LiveReaderWindow(tk.Toplevel):
    """Standalone live reader window - shows game state in real-time."""

    def __init__(self, parent, *, config_path: Path):
        super().__init__(parent)
        self.title("Live Reader")
        self.geometry("280x120")
        self.attributes("-topmost", True)
        self.config_path = config_path
        self.detector = None
        self._load_error = None

        # Try to load detector
        try:
            from screen_capture import GOP3Detector
            self.detector = GOP3Detector(load_config())
            self._load_error = None
        except Exception as exc:
            self._load_error = str(exc)

        self._build_ui()
        self._tick()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        self.player_var = tk.StringVar(value="Player: --")
        self.dealer_var = tk.StringVar(value="Dealer: --")
        self.phase_var = tk.StringVar(value="Phase: --")

        ttk.Label(self, textvariable=self.player_var, font=("Consolas", 14)).pack(anchor="w", **pad)
        ttk.Label(self, textvariable=self.dealer_var, font=("Consolas", 14)).pack(anchor="w", **pad)
        ttk.Label(self, textvariable=self.phase_var, font=("Consolas", 11)).pack(anchor="w", **pad)

        if self._load_error:
            ttk.Label(self, text=f"Error: {self._load_error}", foreground="red").pack(**pad)

    def _tick(self):
        if self.detector:
            try:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    shot = sct.grab(monitor)
                    import numpy as np
                    import cv2
                    img = np.array(shot)
                    screen = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                state = self.detector.detect_game_state(screen)
                pt = state.get("player_total")
                dt = state.get("dealer_total")
                soft = state.get("is_soft", False)
                phase = state.get("phase", "unknown")

                pt_str = f"{'S' if soft else 'H'}{pt}" if pt else "--"
                dt_str = str(dt) if dt else "--"

                self.player_var.set(f"Player: {pt_str}")
                self.dealer_var.set(f"Dealer: {dt_str}")
                self.phase_var.set(f"Phase: {phase}")
            except Exception as exc:
                err = str(exc)[:40]
                self.phase_var.set(f"Error: {err}")

        self.after(150, self._tick)


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
