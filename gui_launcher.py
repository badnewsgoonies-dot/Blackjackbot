"""Simple GUI launcher for GOP3 Blackjack bot tools (Windows)."""

import ctypes
from ctypes import wintypes
import glob
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
        ttk.Button(row4, text="Diagnostic", command=self._open_diagnostic_reader).pack(side="left", padx=6)
        ttk.Button(row4, text="Extract Frames", command=self._extract_frames).pack(side="left", padx=6)
        self._record_btn = ttk.Button(row4, text="Record Frames", command=self._toggle_recording)
        self._record_btn.pack(side="left", padx=6)
        self._recording = False
        self._record_thread = None

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
        # Give user 2 seconds to click on the game window
        self.status.set("Click on the game window within 2 seconds...")
        self.update()
        time.sleep(2)
        title = get_foreground_window_title()
        if title:
            self.config_title.set(title)
            self.status.set(f"Set to: {title}")
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
        # Just bring to foreground without changing window state
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
        seq = ["hit_bet", "stand", "double", "split"]
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
                self.status.set("Launching bot...")
            else:
                self.status.set("Launching bot (game window not found)...")

            # Launch immediately - no F9 gate
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
            self.status.set("Bot running. Press Ctrl+Alt+J to stop.")
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

    def _open_diagnostic_reader(self):
        try:
            DiagnosticReaderWindow(self, config_path=CONFIG_PATH)
        except Exception as exc:
            self.status.set(f"Failed to open diagnostic reader: {exc}")

    def _extract_frames(self):
        """Extract frames from a video file to timing_frames/."""
        from tkinter import filedialog, messagebox
        video_path = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.webm"), ("All files", "*.*")]
        )
        if not video_path:
            return
        
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "timing_frames")
        os.makedirs(output_dir, exist_ok=True)
        
        # Clear existing frames
        for f in glob.glob(os.path.join(output_dir, "frame_*.png")):
            os.remove(f)
        
        self.status.set("Extracting frames...")
        self.update()
        
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_interval = max(1, int(fps / 5))  # Extract at ~5 fps
            
            frame_count = 0
            saved_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_count % frame_interval == 0:
                    timestamp = frame_count / fps
                    out_path = os.path.join(output_dir, f"frame_{saved_count:05d}_{timestamp:.2f}s.png")
                    cv2.imwrite(out_path, frame)
                    saved_count += 1
                frame_count += 1
            cap.release()
            
            self.status.set(f"Extracted {saved_count} frames to timing_frames/")
            messagebox.showinfo("Done", f"Extracted {saved_count} frames at ~5 fps\nRun 'python test_stability_headless.py' to analyze")
        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror("Error", str(e))

    def _toggle_recording(self):
        """Toggle continuous frame recording from screen."""
        if self._recording:
            self._recording = False
            self._record_btn.config(text="Record Frames")
            self.status.set("Recording stopped")
        else:
            self._recording = True
            self._record_btn.config(text="⏹ STOP Recording")
            self._record_thread = threading.Thread(target=self._record_frames_loop, daemon=True)
            self._record_thread.start()

    def _record_frames_loop(self):
        """Background thread that captures frames at ~5 fps."""
        import cv2
        from screen_capture import ScreenCapture
        
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "timing_frames")
        os.makedirs(output_dir, exist_ok=True)
        
        # Clear existing frames
        for f in glob.glob(os.path.join(output_dir, "frame_*.png")):
            os.remove(f)
        
        capture = ScreenCapture()
        frame_count = 0
        start_time = time.time()
        interval = 0.2  # 5 fps
        
        self.after(0, lambda: self.status.set("Recording... click STOP when done"))
        
        while self._recording:
            try:
                screen = capture.capture_screen()
                if screen is not None:
                    timestamp = time.time() - start_time
                    out_path = os.path.join(output_dir, f"frame_{frame_count:05d}_{timestamp:.2f}s.png")
                    cv2.imwrite(out_path, screen)
                    frame_count += 1
                time.sleep(interval)
            except Exception:
                break
        
        self.after(0, lambda: self.status.set(f"Saved {frame_count} frames to timing_frames/"))

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
                required = getattr(load_config(), "REQUIRE_BUTTONS_FOR_ACTION", ("hit_bet", "stand"))
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

        ttk.Button(box1, text="Hit/Bet", command=lambda: self._move_to("hit_bet")).grid(row=1, column=0, padx=6, pady=4)
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
        self._running = True

        ttk.Label(self, textvariable=self.player_var, font=("Consolas", 14)).pack(anchor="w", **pad)
        ttk.Label(self, textvariable=self.dealer_var, font=("Consolas", 14)).pack(anchor="w", **pad)
        ttk.Label(self, textvariable=self.phase_var, font=("Consolas", 11)).pack(anchor="w", **pad)

        if self._load_error:
            ttk.Label(self, text=f"Error: {self._load_error}", foreground="red").pack(**pad)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._running = False
        self.destroy()

    def _tick(self):
        if not self._running:
            return
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
            except Exception:
                pass  # Silently ignore errors during shutdown

        if self._running:
            self.after(150, self._tick)


class DiagnosticReaderWindow(tk.Toplevel):
    """Enhanced diagnostic window - full state vector with stability tracking.
    
    Features:
    - State signature stability (phase + buttons + player_total only)
    - Instability event capture (saves frame + state + diff on change)
    - Shows "what is changing" in UI
    - Confidence gating (rejects out-of-range totals, impossible jumps)
    - Recording toggle for offline debugging
    """

    STABILITY_WINDOW = 5  # Frames to track for stability
    MAX_EVENTS = 200  # Max events to keep on disk
    VALID_TOTAL_RANGE = (2, 31)  # Valid player total range
    MAX_JUMP = 11  # Max valid total change in one frame (hit an Ace)

    def __init__(self, parent, *, config_path: Path):
        super().__init__(parent)
        self.title("Diagnostic Reader")
        self.geometry("480x480")
        self.attributes("-topmost", True)
        self.config_path = config_path
        self.detector = None
        self._load_error = None
        self._running = True

        # State history for stability tracking
        self._history = []  # List of (signature, full_state, screen) tuples
        self._frame_count = 0
        self._start_time = time.time()
        self._last_signature = None
        self._last_stable_signature = None
        self._events_dir = Path("diagnostics/events")
        self._recording = False
        self._event_count = 0

        # Try to load detector
        try:
            from screen_capture import GOP3Detector
            self.detector = GOP3Detector(load_config())
        except Exception as exc:
            self._load_error = str(exc)

        self._build_ui()
        self._tick()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 3}

        # Header
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=6)
        self.frame_var = tk.StringVar(value="Frame: 0 | FPS: --")
        ttk.Label(header, textvariable=self.frame_var, font=("Consolas", 9)).pack(side="left")
        self.stability_var = tk.StringVar(value="Stability: --")
        ttk.Label(header, textvariable=self.stability_var, font=("Consolas", 9, "bold")).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # State section
        state_frame = ttk.LabelFrame(self, text="Detected State")
        state_frame.pack(fill="x", padx=10, pady=4)

        self.phase_var = tk.StringVar(value="Phase: --")
        ttk.Label(state_frame, textvariable=self.phase_var, font=("Consolas", 12, "bold")).pack(anchor="w", **pad)

        totals_row = ttk.Frame(state_frame)
        totals_row.pack(fill="x", **pad)
        self.player_var = tk.StringVar(value="Player: --")
        self.dealer_var = tk.StringVar(value="Dealer: --")
        ttk.Label(totals_row, textvariable=self.player_var, font=("Consolas", 11)).pack(side="left", padx=(0, 20))
        ttk.Label(totals_row, textvariable=self.dealer_var, font=("Consolas", 11)).pack(side="left")

        # Confidence indicator
        self.confidence_var = tk.StringVar(value="Confidence: --")
        ttk.Label(state_frame, textvariable=self.confidence_var, font=("Consolas", 10)).pack(anchor="w", **pad)

        # Buttons section
        btn_frame = ttk.LabelFrame(self, text="Button Visibility")
        btn_frame.pack(fill="x", padx=10, pady=4)

        self.btn_vars = {}
        btn_row = ttk.Frame(btn_frame)
        btn_row.pack(fill="x", **pad)
        for btn_name in ["hit_bet", "stand", "double", "split"]:
            var = tk.StringVar(value=f"{btn_name}: ?")
            self.btn_vars[btn_name] = var
            ttk.Label(btn_row, textvariable=var, font=("Consolas", 10)).pack(side="left", padx=6)

        # Change indicator
        self.change_var = tk.StringVar(value="Changes: --")
        ttk.Label(self, textvariable=self.change_var, font=("Consolas", 10), foreground="red").pack(anchor="w", padx=10, pady=2)

        # History section
        hist_frame = ttk.LabelFrame(self, text=f"Last {self.STABILITY_WINDOW} Signatures")
        hist_frame.pack(fill="both", expand=True, padx=10, pady=4)

        self.hist_text = tk.Text(hist_frame, height=6, font=("Consolas", 9), state="disabled", wrap="none")
        self.hist_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Recording status
        self.record_var = tk.StringVar(value="Recording: OFF")
        ttk.Label(self, textvariable=self.record_var, font=("Consolas", 9)).pack(anchor="w", padx=10)

        # Controls
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill="x", padx=10, pady=6)
        ttk.Button(ctrl_frame, text="Reset", command=self._reset).pack(side="left")
        self.record_btn = ttk.Button(ctrl_frame, text="Start Recording", command=self._toggle_recording)
        self.record_btn.pack(side="left", padx=6)
        ttk.Button(ctrl_frame, text="Snapshot", command=self._save_stable_snapshot).pack(side="left", padx=6)
        ttk.Button(ctrl_frame, text="Open Events", command=self._open_events_folder).pack(side="left", padx=6)
        ttk.Button(ctrl_frame, text="Close", command=self._on_close).pack(side="right")

        if self._load_error:
            ttk.Label(self, text=f"Error: {self._load_error}", foreground="red").pack(padx=10, pady=4)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _reset(self):
        self._history.clear()
        self._frame_count = 0
        self._start_time = time.time()
        self._last_signature = None
        self._last_stable_signature = None

    def _toggle_recording(self):
        self._recording = not self._recording
        if self._recording:
            self._events_dir.mkdir(parents=True, exist_ok=True)
            self.record_btn.config(text="Stop Recording")
            self.record_var.set(f"Recording: ON -> {self._events_dir}")
        else:
            self.record_btn.config(text="Start Recording")
            self.record_var.set("Recording: OFF")

    def _open_events_folder(self):
        self._events_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(self._events_dir))

    def _on_close(self):
        self._running = False
        self.destroy()

    def _make_signature(self, state: dict) -> tuple:
        """Create a stability signature from state.
        
        Signature includes: phase, button mask, player_total (not dealer, not soft).
        This is intentionally small to avoid noise from unreliable fields.
        """
        phase = state.get("phase", "unknown")
        buttons = state.get("buttons", {})
        btn_mask = tuple(sorted(buttons.keys()))
        player_total = state.get("player_total")
        return (phase, btn_mask, player_total)

    def _validate_total(self, total, prev_total) -> tuple:
        """Validate a total reading. Returns (is_valid, reason)."""
        if total is None:
            return (True, "none")  # None is valid
        if not isinstance(total, int):
            return (False, "not_int")
        if total < self.VALID_TOTAL_RANGE[0] or total > self.VALID_TOTAL_RANGE[1]:
            return (False, f"out_of_range:{total}")
        if prev_total is not None and abs(total - prev_total) > self.MAX_JUMP:
            return (False, f"jump:{prev_total}->{total}")
        return (True, "ok")

    def _compute_diff(self, old_sig, new_sig) -> list:
        """Compute what changed between two signatures."""
        if old_sig is None:
            return ["initial"]
        changes = []
        if old_sig[0] != new_sig[0]:
            changes.append(f"phase:{old_sig[0]}->{new_sig[0]}")
        if old_sig[1] != new_sig[1]:
            old_btns = set(old_sig[1])
            new_btns = set(new_sig[1])
            added = new_btns - old_btns
            removed = old_btns - new_btns
            if added:
                changes.append(f"+btns:{','.join(added)}")
            if removed:
                changes.append(f"-btns:{','.join(removed)}")
        if old_sig[2] != new_sig[2]:
            changes.append(f"player:{old_sig[2]}->{new_sig[2]}")
        return changes if changes else ["no_change"]

    def _save_event(self, screen, state: dict, signature: tuple, diff: list, reason: str = "change", force: bool = False):
        """Save an instability event to disk with ROI crops, meta, and tight circle crop."""
        if not self._recording and not force:
            return
        import cv2
        import hashlib
        
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        timestamp_ms = int(time.time() * 1000)
        prefix = "stable" if reason == "snapshot" else "event"
        event_dir = self._events_dir / f"{prefix}_{timestamp}_{self._event_count:04d}"
        event_dir.mkdir(parents=True, exist_ok=True)
        self._event_count += 1

        h, w = screen.shape[:2]

        # Save full frame
        cv2.imwrite(str(event_dir / "frame.png"), screen)

        # Get ROI rectangles and save crops
        rois = self._get_roi_rectangles(screen)
        
        for roi_name, rect in rois.items():
            if rect:
                x1, y1, x2, y2 = rect
                roi_img = screen[y1:y2, x1:x2]
                if roi_img.size > 0:
                    cv2.imwrite(str(event_dir / f"roi_{roi_name}.png"), roi_img)

        # Save tight blue circle crop (for player total)
        circle_rect = self._find_blue_circle_tight(screen, rois.get("player_total"))
        if circle_rect:
            cx1, cy1, cx2, cy2 = circle_rect
            circle_img = screen[cy1:cy2, cx1:cx2]
            if circle_img.size > 0:
                cv2.imwrite(str(event_dir / "roi_player_circle_tight.png"), circle_img)
            rois["player_circle_tight"] = circle_rect

        # Build signature strings
        sig_str = self._signature_to_string(signature)
        prev_sig_str = self._signature_to_string(self._last_signature) if self._last_signature else None

        # Determine change reason
        change_reasons = []
        if diff:
            for d in diff:
                if "phase:" in d:
                    change_reasons.append("phase_change")
                elif "btns:" in d:
                    change_reasons.append("button_mask_change")
                elif "player:" in d:
                    change_reasons.append("player_total_change")

        # Save meta.json
        meta = {
            "timestamp": timestamp,
            "timestamp_ms": timestamp_ms,
            "frame": self._frame_count,
            "fps": self._frame_count / (time.time() - self._start_time) if (time.time() - self._start_time) > 0 else 0,
            "screen_w": w,
            "screen_h": h,
            "window_title": self._get_foreground_title(),
            "calibration_status": self._get_calibration_status(),
            "config_hash": self._get_config_hash(),
            "reason": reason,
        }
        with open(event_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        # Save state with ROI rectangles
        state_copy = dict(state)
        state_copy["buttons"] = {k: list(v) for k, v in state.get("buttons", {}).items()}
        state_copy["roi_rectangles"] = {k: list(v) if v else None for k, v in rois.items()}
        with open(event_dir / "state.json", "w") as f:
            json.dump(state_copy, f, indent=2)

        # Save diff with compact signatures and reasons
        with open(event_dir / "diff.json", "w") as f:
            json.dump({
                "sig_before": prev_sig_str,
                "sig_after": sig_str,
                "changes": diff,
                "change_reasons": change_reasons if change_reasons else ["unknown"],
                "frame": self._frame_count,
                "timestamp": timestamp,
            }, f, indent=2)

        # Cleanup old events
        self._cleanup_old_events()

    def _signature_to_string(self, sig: tuple) -> str:
        """Convert signature tuple to compact string like 'player_turn|0b1111|17'."""
        if not sig:
            return "None"
        phase = sig[0] if sig[0] else "?"
        # Convert button tuple to bitmask: hit_bet=1, stand=2, double=4, split=8
        btn_order = ["hit_bet", "stand", "double", "split"]
        mask = 0
        if sig[1]:
            for i, btn in enumerate(btn_order):
                if btn in sig[1]:
                    mask |= (1 << i)
        player = sig[2] if sig[2] is not None else "?"
        return f"{phase}|0b{mask:04b}|{player}"

    def _find_blue_circle_tight(self, screen, player_roi_rect) -> tuple:
        """Find tight bounding box around the blue circle in player total region."""
        if not player_roi_rect:
            return None
        try:
            import cv2
            import numpy as np
            
            x1, y1, x2, y2 = player_roi_rect
            roi = screen[y1:y2, x1:x2]
            if roi.size == 0:
                return None
                
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            config = self.detector.config if self.detector else None
            lower = np.array(getattr(config, 'BLUE_CIRCLE_HSV_LOWER', (70, 30, 40)) if config else (70, 30, 40))
            upper = np.array(getattr(config, 'BLUE_CIRCLE_HSV_UPPER', (140, 255, 255)) if config else (140, 255, 255))
            mask = cv2.inRange(hsv, lower, upper)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
                
            # Find largest contour
            largest = max(contours, key=cv2.contourArea)
            bx, by, bw, bh = cv2.boundingRect(largest)
            
            # Convert back to screen coordinates
            return (x1 + bx, y1 + by, x1 + bx + bw, y1 + by + bh)
        except Exception:
            return None

    def _get_foreground_title(self) -> str:
        """Get current foreground window title."""
        try:
            return get_foreground_window_title()
        except Exception:
            return "unknown"

    def _get_calibration_status(self) -> str:
        """Get auto-calibration status."""
        try:
            if self.detector and hasattr(self.detector, 'auto_cal'):
                transform = getattr(self.detector.auto_cal, 'transform', None)
                if transform:
                    return f"ok_scale_{transform.scale:.3f}"
            return "no_transform"
        except Exception:
            return "error"

    def _get_config_hash(self) -> str:
        """Get a short hash of current config for drift detection."""
        try:
            config = self.detector.config if self.detector else None
            if not config:
                return "no_config"
            # Hash key config values
            key_vals = [
                str(getattr(config, 'PLAYER_TOTAL_REGION', '')),
                str(getattr(config, 'BUTTON_POSITIONS', '')),
                str(getattr(config, 'SCREEN_WIDTH', '')),
                str(getattr(config, 'SCREEN_HEIGHT', '')),
            ]
            import hashlib
            return hashlib.md5("|".join(key_vals).encode()).hexdigest()[:8]
        except Exception:
            return "error"

    def _save_stable_snapshot(self):
        """Manually save a snapshot of current stable state (for baseline dataset)."""
        if not self.detector or not self._history:
            return
        try:
            import mss
            import numpy as np
            import cv2
            
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                img = np.array(shot)
                screen = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            state = self.detector.detect_game_state(screen)
            signature = self._make_signature(state)
            self._events_dir.mkdir(parents=True, exist_ok=True)
            self._save_event(screen, state, signature, ["manual_snapshot"], reason="snapshot", force=True)
            self.record_var.set(f"Snapshot saved: event {self._event_count - 1}")
        except Exception as e:
            self.record_var.set(f"Snapshot failed: {e}")

    def _get_roi_rectangles(self, screen) -> dict:
        """Get ROI rectangles for player_total, dealer_total, and buttons."""
        rois = {
            "player_total": None,
            "dealer_total": None,
            "buttons": None,
        }
        
        if not self.detector:
            return rois
            
        try:
            config = self.detector.config
            h, w = screen.shape[:2]
            
            # Player total region
            region = getattr(config, 'PLAYER_TOTAL_REGION', None)
            if region:
                rois["player_total"] = self._percent_region_to_rect(region, w, h)
            
            # Dealer total region
            region = getattr(config, 'DEALER_TOTAL_REGION', None)
            if not region:
                region = getattr(config, 'DEALER_CARD_REGION', None)
            if region:
                rois["dealer_total"] = self._percent_region_to_rect(region, w, h)
            
            # Button detection region
            region = getattr(config, 'BUTTON_DETECT_REGION', None)
            if region:
                rois["buttons"] = self._percent_region_to_rect(region, w, h)
                
        except Exception:
            pass
            
        return rois

    def _percent_region_to_rect(self, region: dict, w: int, h: int) -> tuple:
        """Convert a percent-based region to (x1, y1, x2, y2) rectangle."""
        x_pct = region.get('x_percent', (0, 1))
        y_pct = region.get('y_percent', (0, 1))
        # Handle both tuple and list formats
        if isinstance(x_pct, (list, tuple)) and len(x_pct) >= 2:
            x1 = int(w * x_pct[0])
            x2 = int(w * x_pct[1])
        else:
            x1, x2 = 0, w
        if isinstance(y_pct, (list, tuple)) and len(y_pct) >= 2:
            y1 = int(h * y_pct[0])
            y2 = int(h * y_pct[1])
        else:
            y1, y2 = 0, h
        return (x1, y1, x2, y2)

    def _cleanup_old_events(self):
        """Keep only last MAX_EVENTS events."""
        try:
            events = sorted(self._events_dir.iterdir())
            if len(events) > self.MAX_EVENTS:
                for old in events[:-self.MAX_EVENTS]:
                    if old.is_dir():
                        import shutil
                        shutil.rmtree(old)
        except Exception:
            pass

    def _compute_stability(self) -> tuple:
        """Compute stability metrics from signature history."""
        if len(self._history) < self.STABILITY_WINDOW:
            return (False, f"need {self.STABILITY_WINDOW - len(self._history)} more")

        recent_sigs = [h[0] for h in self._history[-self.STABILITY_WINDOW:]]
        if len(set(recent_sigs)) > 1:
            # Find what's changing
            first = recent_sigs[0]
            for sig in recent_sigs[1:]:
                if sig != first:
                    diff = self._compute_diff(first, sig)
                    return (False, " ".join(diff[:2]))
            return (False, "unstable")

        return (True, "STABLE")

    def _tick(self):
        if not self._running:
            return

        self._frame_count += 1
        elapsed = time.time() - self._start_time
        fps = self._frame_count / elapsed if elapsed > 0 else 0

        if self.detector:
            try:
                import mss
                import numpy as np
                import cv2

                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    shot = sct.grab(monitor)
                    img = np.array(shot)
                    screen = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                state = self.detector.detect_game_state(screen)
                signature = self._make_signature(state)

                # Validate player total
                prev_player = self._history[-1][1].get("player_total") if self._history else None
                is_valid, valid_reason = self._validate_total(state.get("player_total"), prev_player)

                # Compute diff from last frame
                diff = self._compute_diff(self._last_signature, signature)

                # Record if signature changed and recording is on
                if self._last_signature is not None and signature != self._last_signature:
                    self._save_event(screen, state, signature, diff)

                # Update history
                self._history.append((signature, state, None))  # Don't store screen in memory
                if len(self._history) > self.STABILITY_WINDOW * 2:
                    self._history = self._history[-self.STABILITY_WINDOW * 2:]
                self._last_signature = signature

                # Update displays
                pt = state.get("player_total")
                dt = state.get("dealer_total")
                soft = state.get("is_soft", False)
                phase = state.get("phase", "unknown")
                buttons = state.get("buttons", {})

                pt_str = f"{'S' if soft else 'H'}{pt}" if pt is not None else "--"
                dt_str = str(dt) if dt is not None else "--"

                self.frame_var.set(f"Frame: {self._frame_count} | FPS: {fps:.1f}")
                self.phase_var.set(f"Phase: {phase}")
                self.player_var.set(f"Player: {pt_str}")
                self.dealer_var.set(f"Dealer: {dt_str}")
                self.confidence_var.set(f"Confidence: {valid_reason}")

                for btn_name, var in self.btn_vars.items():
                    if btn_name in buttons:
                        var.set(f"{btn_name}: OK")
                    else:
                        var.set(f"{btn_name}: --")

                # Show changes
                if diff and diff != ["no_change"] and diff != ["initial"]:
                    self.change_var.set(f"Changes: {' | '.join(diff)}")
                else:
                    self.change_var.set("Changes: --")

                # Stability
                is_stable, reason = self._compute_stability()
                self.stability_var.set(f"Stability: {reason}")
                if is_stable:
                    self._last_stable_signature = signature

                # History display
                self.hist_text.config(state="normal")
                self.hist_text.delete("1.0", "end")
                for i, (sig, st, _) in enumerate(self._history[-self.STABILITY_WINDOW:]):
                    phase_s = sig[0][:7] if sig[0] else "?"
                    btns_s = ",".join(sig[1])[:15] if sig[1] else "--"
                    pt_s = sig[2] if sig[2] is not None else "--"
                    line = f"{i+1}: {phase_s:8} btns=[{btns_s:15}] P:{pt_s}\n"
                    self.hist_text.insert("end", line)
                self.hist_text.config(state="disabled")

            except Exception as e:
                self.phase_var.set(f"Error: {e}")

        if self._running:
            self.after(100, self._tick)


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
