"""Print the current foreground window title (Windows)."""

import ctypes


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


if __name__ == "__main__":
    title = get_foreground_window_title()
    if title:
        print(title)
    else:
        print("(no foreground window title detected)")
