from __future__ import annotations

import ctypes
import os
import sys
import threading
from pathlib import Path
from typing import Callable

import pythoncom
import win32api
import win32com.client
import win32con
import win32gui


APP_NAME = "DesktopFloatingWindow"
STARTUP_SHORTCUT_NAME = "DesktopFloatingWindow.lnk"
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
GCL_STYLE = -26
CS_DROPSHADOW = 0x00020000


def get_startup_shortcut_path() -> Path:
    appdata = Path(os.environ["APPDATA"])
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / STARTUP_SHORTCUT_NAME


def normalize_path(value: str | Path) -> str:
    try:
        return str(Path(value).resolve()).lower()
    except OSError:
        return str(value).lower()


def apply_native_window_style(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    try:
        dark_mode = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_mode),
            ctypes.sizeof(dark_mode),
        )
        corner = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner),
            ctypes.sizeof(corner),
        )
    except Exception:
        pass

    try:
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            get_class_long = user32.GetClassLongPtrW
            set_class_long = user32.SetClassLongPtrW
        else:
            get_class_long = user32.GetClassLongW
            set_class_long = user32.SetClassLongW
        style = get_class_long(hwnd, GCL_STYLE)
        if not style & CS_DROPSHADOW:
            set_class_long(hwnd, GCL_STYLE, style | CS_DROPSHADOW)
            win32gui.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE
                | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE
                | win32con.SWP_NOZORDER
                | win32con.SWP_FRAMECHANGED,
            )
    except Exception:
        pass


def apply_click_through(hwnd: int, enabled: bool) -> None:
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if enabled:
        ex_style |= win32con.WS_EX_TRANSPARENT
    else:
        ex_style &= ~win32con.WS_EX_TRANSPARENT
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE
        | win32con.SWP_NOSIZE
        | win32con.SWP_NOACTIVATE
        | win32con.SWP_NOZORDER
        | win32con.SWP_FRAMECHANGED,
    )


def get_work_area(hwnd: int, screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    try:
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(monitor)
        return tuple(info["Work"])
    except Exception:
        return 0, 0, screen_width, screen_height


class StartupManager:
    def __init__(self, app_dir: Path, script_path: Path) -> None:
        self.app_dir = app_dir
        self.script_path = script_path
        self.shortcut_path = get_startup_shortcut_path()

    def _launch_spec(self) -> tuple[str, str, str, str]:
        if getattr(sys, "frozen", False):
            target = str(Path(sys.executable).resolve())
            arguments = ""
            icon_source = target
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            target = str((pythonw if pythonw.exists() else Path(sys.executable)).resolve())
            arguments = f'"{self.script_path.resolve()}"'
            icon_source = target
        return target, arguments, str(self.app_dir), icon_source

    def is_enabled(self) -> bool:
        return self.shortcut_path.exists()

    def shortcut_matches_current(self) -> bool:
        if not self.shortcut_path.exists():
            return False
        pythoncom.CoInitialize()
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(self.shortcut_path))
            target, arguments, _, _ = self._launch_spec()
            return normalize_path(shortcut.Targetpath) == normalize_path(target) and shortcut.Arguments == arguments
        finally:
            pythoncom.CoUninitialize()

    def sync_if_needed(self) -> bool:
        if not self.shortcut_path.exists() or self.shortcut_matches_current():
            return False
        self.set_enabled(True)
        return True

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            target, arguments, workdir, icon_source = self._launch_spec()
            self.shortcut_path.parent.mkdir(parents=True, exist_ok=True)
            pythoncom.CoInitialize()
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(str(self.shortcut_path))
                shortcut.Targetpath = target
                shortcut.Arguments = arguments
                shortcut.WorkingDirectory = workdir
                shortcut.IconLocation = f"{icon_source},0"
                shortcut.Description = "桌面浮窗开机自启"
                shortcut.Save()
            finally:
                pythoncom.CoUninitialize()
            return
        if self.shortcut_path.exists():
            self.shortcut_path.unlink()


class TrayController:
    WM_TRAYICON = win32con.WM_USER + 20
    CMD_SHOW = 1101
    CMD_HIDE = 1102
    CMD_TOPMOST = 1103
    CMD_STARTUP = 1104
    CMD_EXIT = 1105

    def __init__(
        self,
        get_state: Callable[[], dict[str, bool]],
        dispatch: Callable[[str], None],
    ) -> None:
        self.get_state = get_state
        self.dispatch = dispatch
        self.class_name = f"{APP_NAME}Tray{os.getpid()}"
        self.hwnd: int | None = None
        self.icon_handle: int | None = None
        self.thread: threading.Thread | None = None
        self.ready = threading.Event()
        self.available = False

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=3)

    def stop(self) -> None:
        if self.hwnd:
            try:
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except win32gui.error:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def refresh_icon(self) -> None:
        if not self.hwnd or not self.available:
            return
        nid = (
            self.hwnd,
            0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            self.WM_TRAYICON,
            self._load_icon(),
            "专注浮窗 - 右键打开菜单",
        )
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except win32gui.error:
            self.available = False

    def _load_icon(self) -> int:
        if self.icon_handle:
            return self.icon_handle
        try:
            if getattr(sys, "frozen", False):
                self.icon_handle = win32gui.LoadImage(
                    0,
                    str(Path(sys.executable).resolve()),
                    win32con.IMAGE_ICON,
                    0,
                    0,
                    win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
                )
        except win32gui.error:
            self.icon_handle = None
        if not self.icon_handle:
            self.icon_handle = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        return self.icon_handle

    def _run(self) -> None:
        message_map = {
            win32con.WM_COMMAND: self._on_command,
            win32con.WM_DESTROY: self._on_destroy,
            win32con.WM_CLOSE: self._on_close,
            self.WM_TRAYICON: self._on_tray_event,
        }
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = self.class_name
        wc.lpfnWndProc = message_map
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error:
            pass
        self.hwnd = win32gui.CreateWindow(
            self.class_name,
            self.class_name,
            win32con.WS_OVERLAPPED | win32con.WS_SYSMENU,
            0,
            0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0,
            0,
            wc.hInstance,
            None,
        )
        win32gui.UpdateWindow(self.hwnd)
        nid = (
            self.hwnd,
            0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            self.WM_TRAYICON,
            self._load_icon(),
            "专注浮窗 - 右键打开菜单",
        )
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
            self.available = True
        except win32gui.error:
            self.available = False
        self.ready.set()
        win32gui.PumpMessages()

    def _show_menu(self) -> None:
        if not self.hwnd:
            return
        state = self.get_state()
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(
            menu,
            win32con.MF_STRING,
            self.CMD_SHOW if not state["visible"] else self.CMD_HIDE,
            "显示主窗口" if not state["visible"] else "收进托盘",
        )
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        self._append_toggle(menu, self.CMD_TOPMOST, "窗口置顶", state["topmost"])
        self._append_toggle(menu, self.CMD_STARTUP, "开机自启", state["startup"])
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.CMD_EXIT, "退出程序")
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_LEFTALIGN | win32con.TPM_BOTTOMALIGN | win32con.TPM_RIGHTBUTTON,
            pos[0],
            pos[1],
            0,
            self.hwnd,
            None,
        )
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def _append_toggle(self, menu: int, command_id: int, text: str, enabled: bool) -> None:
        flags = win32con.MF_STRING | (win32con.MF_CHECKED if enabled else win32con.MF_UNCHECKED)
        win32gui.AppendMenu(menu, flags, command_id, text)

    def _on_tray_event(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
            self.dispatch("show")
            return 0
        if lparam in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
            self._show_menu()
            return 0
        return 0

    def _on_command(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        command_id = win32api.LOWORD(wparam)
        action_map = {
            self.CMD_SHOW: "show",
            self.CMD_HIDE: "hide",
            self.CMD_TOPMOST: "topmost",
            self.CMD_STARTUP: "startup",
            self.CMD_EXIT: "exit",
        }
        action = action_map.get(command_id)
        if action:
            self.dispatch(action)
        return 0

    def _on_close(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        win32gui.DestroyWindow(hwnd)
        return 0

    def _on_destroy(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
        except win32gui.error:
            pass
        win32gui.PostQuitMessage(0)
        return 0
