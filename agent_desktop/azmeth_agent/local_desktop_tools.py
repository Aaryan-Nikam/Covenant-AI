from __future__ import annotations

import shutil
import subprocess
import time
import webbrowser
from datetime import UTC, datetime
from pathlib import Path

from azmeth_agent.tools import Observation


def scale_point(
    x: int,
    y: int,
    capture_size: tuple[int, int] | None,
    screen_size: tuple[int, int],
) -> tuple[int, int]:
    """Map screenshot-coordinate points to real input-coordinate points."""

    screen_width, screen_height = screen_size
    if capture_size is None:
        scaled_x = x
        scaled_y = y
    else:
        capture_width, capture_height = capture_size
        scaled_x = round(x * (screen_width / capture_width))
        scaled_y = round(y * (screen_height / capture_height))
    return (
        min(max(scaled_x, 0), screen_width - 1),
        min(max(scaled_y, 0), screen_height - 1),
    )


class LocalDesktopTools:
    """Local OS-level adapter.

    This adapter deliberately uses screenshot, mouse, keyboard, and file chooser
    interactions. It does not inspect the DOM, execute JavaScript, or call browser
    internals.
    """

    def __init__(self, evidence_dir: Path, notification_command: tuple[str, ...] | None = None) -> None:
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.notification_command = notification_command
        self._pyautogui = self._import_pyautogui()
        self._last_capture_size: tuple[int, int] | None = None

    def open_url(self, url: str) -> None:
        webbrowser.open(url)
        time.sleep(2)

    def observe(self) -> Observation:
        screenshot_path = self.evidence_dir / f"{self._timestamp()}-screenshot.png"
        screenshot = self._pyautogui.screenshot()
        self._last_capture_size = screenshot.size
        screenshot.save(screenshot_path)
        return Observation(
            screenshot_path=screenshot_path,
            screen_text="",
            current_url=None,
        )

    def click(self, x: int, y: int) -> None:
        px, py = scale_point(
            x,
            y,
            self._last_capture_size,
            tuple(self._pyautogui.size()),
        )
        self._pyautogui.moveTo(px, py, duration=0.2)
        self._pyautogui.click()

    def type_text(self, text: str) -> None:
        copied = self._copy_to_clipboard(text)
        if copied:
            self.hotkey(self._paste_keys())
            return
        self._pyautogui.write(text, interval=0.01)

    def hotkey(self, keys: tuple[str, ...]) -> None:
        self._pyautogui.hotkey(*keys)

    def scroll(self, amount: int) -> None:
        self._pyautogui.scroll(amount)

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)

    def upload_file(self, path: Path) -> None:
        # Assumes the native file chooser is already open.
        absolute_path = str(path.expanduser().resolve())
        copied = self._copy_to_clipboard(absolute_path)
        if copied:
            self.hotkey(self._paste_keys())
        else:
            self._pyautogui.write(absolute_path, interval=0.01)
        self._pyautogui.press("enter")
        time.sleep(1)

    def notify_human(self, message: str) -> None:
        if self.notification_command:
            subprocess.run([*self.notification_command, message], check=False)
            return
        print(f"[Azmeth Agent] Human attention required: {message}")

    @staticmethod
    def _import_pyautogui():
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError(
                "LocalDesktopTools requires pyautogui. Install client agent dependencies first."
            ) from exc
        pyautogui.FAILSAFE = True
        return pyautogui

    @staticmethod
    def _copy_to_clipboard(text: str) -> bool:
        pbcopy = shutil.which("pbcopy")
        if pbcopy:
            subprocess.run([pbcopy], input=text.encode("utf-8"), check=False)
            return True
        xclip = shutil.which("xclip")
        if xclip:
            subprocess.run([xclip, "-selection", "clipboard"], input=text.encode("utf-8"), check=False)
            return True
        return False

    @staticmethod
    def _paste_keys() -> tuple[str, ...]:
        return ("command", "v") if shutil.which("pbcopy") else ("ctrl", "v")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
