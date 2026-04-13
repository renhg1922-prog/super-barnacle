from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

from desktop_features import StartupManager, TrayController, apply_native_window_style


APP_NAME = "DesktopFloatingWindow"
SETTINGS_FILENAME = "floating_window_settings.json"
RUNTIME_REPORT_FILENAME = "portable_runtime_report.json"
THEME = {
    "window": "#0F141B",
    "panel": "#17202A",
    "panel_alt": "#111921",
    "header": "#1A2530",
    "accent": "#D3A757",
    "accent_soft": "#423217",
    "text": "#F4EFE5",
    "muted": "#9AA7B7",
    "line": "#2F3D4A",
    "button": "#243341",
    "button_hover": "#314555",
    "danger": "#B64D57",
    "danger_hover": "#C75D67",
}
DEFAULT_SETTINGS: dict[str, Any] = {
    "title": "专注浮窗",
    "width": 520,
    "height": 430,
    "x": 96,
    "y": 96,
    "alpha": 0.98,
    "topmost": True,
    "settings_expanded": False,
    "content": "这里写便签内容。\n\n这个版本把界面重点放回正文区域。",
}


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def merge_settings(raw_settings: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    if raw_settings:
        merged.update(raw_settings)

    merged["width"] = max(380, int(merged.get("width", DEFAULT_SETTINGS["width"])))
    merged["height"] = max(300, int(merged.get("height", DEFAULT_SETTINGS["height"])))
    merged["x"] = int(merged.get("x", DEFAULT_SETTINGS["x"]))
    merged["y"] = int(merged.get("y", DEFAULT_SETTINGS["y"]))
    merged["alpha"] = min(1.0, max(0.72, float(merged.get("alpha", DEFAULT_SETTINGS["alpha"]))))
    merged["topmost"] = bool(merged.get("topmost", DEFAULT_SETTINGS["topmost"]))
    merged["settings_expanded"] = bool(merged.get("settings_expanded", DEFAULT_SETTINGS["settings_expanded"]))
    merged["title"] = str(merged.get("title", DEFAULT_SETTINGS["title"]))[:40] or DEFAULT_SETTINGS["title"]
    merged["content"] = str(merged.get("content", DEFAULT_SETTINGS["content"]))
    return merged


class SettingsStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.settings_path = self.base_dir / SETTINGS_FILENAME
        self.runtime_report_path = self.base_dir / RUNTIME_REPORT_FILENAME

    def load(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return dict(DEFAULT_SETTINGS)
        try:
            return merge_settings(json.loads(self.settings_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            return dict(DEFAULT_SETTINGS)

    def save(self, settings: dict[str, Any]) -> None:
        merged = merge_settings(settings)
        temp_path = self.settings_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.settings_path)

    def write_runtime_report(self, settings: dict[str, Any]) -> Path:
        report = {
            "app_name": APP_NAME,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "frozen": bool(getattr(sys, "frozen", False)),
            "cwd": str(Path.cwd()),
            "python_executable": sys.executable,
            "app_dir": str(self.base_dir),
            "settings_path": str(self.settings_path),
            "settings_exists": self.settings_path.exists(),
            "window_title": settings["title"],
            "topmost": settings["topmost"],
            "settings_expanded": settings["settings_expanded"],
            "alpha": settings["alpha"],
        }
        self.runtime_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.runtime_report_path


class FloatingWindowApp:
    def __init__(self, root: tk.Tk, store: SettingsStore) -> None:
        self.root = root
        self.store = store
        self.settings = self.store.load()
        self.startup_manager = StartupManager(self.store.base_dir, Path(__file__))
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.resize_start_width = 0
        self.resize_start_height = 0
        self.save_after_id: str | None = None
        self.hwnd: int | None = None
        self.is_window_visible = True
        self.is_exiting = False

        self.root.title(self.settings["title"])
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.settings["topmost"])
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=THEME["window"])
        self.root.minsize(380, 300)
        self.root.geometry(
            f"{self.settings['width']}x{self.settings['height']}+{self.settings['x']}+{self.settings['y']}"
        )
        self.root.bind("<Escape>", lambda _event: self.hide_to_tray())
        self.root.bind("<Configure>", self.on_window_configure)

        self.ui_font_family = self.pick_font_family(
            [
                "Microsoft YaHei UI",
                "Microsoft YaHei",
                "PingFang SC",
                "Noto Sans CJK SC",
                "SimHei",
                "Segoe UI",
            ]
        )

        self.header_title_var = tk.StringVar(value=self.settings["title"])
        self.topmost_button_var = tk.StringVar(value="")
        self.startup_button_var = tk.StringVar(value="")
        self.opacity_label_var = tk.StringVar(value="")
        self.settings_hint_var = tk.StringVar(value=f"配置文件保存在 {self.store.settings_path.name}")
        self.icon_font_family = self.pick_font_family(
            [
                "Segoe UI Symbol",
                "Segoe Fluent Icons",
                "Microsoft YaHei UI",
                self.ui_font_family,
            ]
        )

        self.shell = tk.Frame(
            self.root,
            bg=THEME["panel"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["line"],
            padx=1,
            pady=1,
        )
        self.shell.pack(fill="both", expand=True)

        self.inner = tk.Frame(self.shell, bg=THEME["panel_alt"])
        self.inner.pack(fill="both", expand=True)

        self.accent_bar = tk.Frame(self.inner, bg=THEME["accent"], height=4)
        self.accent_bar.pack(fill="x")

        self.header = tk.Frame(self.inner, bg=THEME["header"], padx=12, pady=8)
        self.header.pack(fill="x")

        self.title_label = tk.Label(
            self.header,
            textvariable=self.header_title_var,
            bg=THEME["header"],
            fg=THEME["text"],
            font=(self.ui_font_family, 11, "bold"),
            anchor="w",
        )
        self.title_label.pack(side="left", fill="x", expand=True)

        self.header_controls = tk.Frame(self.header, bg=THEME["header"])
        self.header_controls.pack(side="right")

        self.gear_button = self.make_icon_button(
            self.header_controls,
            "⚙",
            self.toggle_settings_panel,
            font_family=self.icon_font_family,
        )
        self.gear_button.pack(side="left", padx=(0, 6))

        self.minimize_button = self.make_icon_button(self.header_controls, "-", self.hide_to_tray)
        self.minimize_button.pack(side="left", padx=(0, 6))

        self.close_button = self.make_icon_button(
            self.header_controls,
            "×",
            self.quit_app,
            background=THEME["danger"],
            hover=THEME["danger_hover"],
        )
        self.close_button.pack(side="left")

        self.settings_panel = tk.Frame(self.inner, bg=THEME["panel_alt"], padx=12, pady=10)
        self.settings_buttons = tk.Frame(self.settings_panel, bg=THEME["panel_alt"])
        self.settings_buttons.pack(fill="x")

        self.topmost_button = self.make_text_button(
            self.settings_buttons,
            self.topmost_button_var,
            self.toggle_topmost,
            width=9,
        )
        self.topmost_button.pack(side="left", padx=(0, 8))

        self.startup_button = self.make_text_button(
            self.settings_buttons,
            self.startup_button_var,
            self.toggle_startup,
            width=9,
        )
        self.startup_button.pack(side="left", padx=(0, 8))

        self.alpha_down_button = self.make_text_button(self.settings_buttons, "更淡", self.adjust_alpha_down, width=6)
        self.alpha_down_button.pack(side="left", padx=(0, 8))

        self.alpha_up_button = self.make_text_button(self.settings_buttons, "更实", self.adjust_alpha_up, width=6)
        self.alpha_up_button.pack(side="left", padx=(0, 12))

        self.opacity_label = tk.Label(
            self.settings_buttons,
            textvariable=self.opacity_label_var,
            bg=THEME["panel_alt"],
            fg=THEME["muted"],
            font=(self.ui_font_family, 9),
            anchor="w",
        )
        self.opacity_label.pack(side="left")

        self.settings_hint = tk.Label(
            self.settings_panel,
            textvariable=self.settings_hint_var,
            bg=THEME["panel_alt"],
            fg=THEME["muted"],
            font=(self.ui_font_family, 8),
            anchor="w",
        )
        self.settings_hint.pack(fill="x", pady=(8, 0))

        self.editor_shell = tk.Frame(self.inner, bg=THEME["panel_alt"], padx=12, pady=12)
        self.editor_shell.pack(fill="both", expand=True)

        self.text_box = tk.Text(
            self.editor_shell,
            wrap="word",
            bg=THEME["window"],
            fg=THEME["text"],
            insertbackground=THEME["accent"],
            relief="flat",
            padx=18,
            pady=18,
            font=(self.ui_font_family, 11),
            spacing1=3,
            spacing3=4,
            undo=True,
            highlightthickness=1,
            highlightbackground=THEME["line"],
            highlightcolor=THEME["line"],
        )
        self.text_box.pack(fill="both", expand=True)
        self.text_box.insert("1.0", self.settings["content"])
        self.text_box.bind("<KeyRelease>", self.on_text_changed)

        self.resize_grip = tk.Canvas(
            self.inner,
            width=18,
            height=18,
            bg=THEME["panel_alt"],
            highlightthickness=0,
            bd=0,
            cursor="size_nw_se",
        )
        self.resize_grip.create_line(6, 16, 16, 6, fill=THEME["muted"], width=1)
        self.resize_grip.create_line(10, 16, 16, 10, fill=THEME["muted"], width=1)
        self.resize_grip.create_line(13, 16, 16, 13, fill=THEME["muted"], width=1)
        self.resize_grip.place(relx=1.0, rely=1.0, x=-6, y=-6, anchor="se")
        self.resize_grip.bind("<ButtonPress-1>", self.start_resize)
        self.resize_grip.bind("<B1-Motion>", self.on_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self.stop_resize)

        for widget in (
            self.header,
            self.title_label,
        ):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.on_drag)
            widget.bind("<ButtonRelease-1>", self.stop_drag)

        self.tray = TrayController(self.get_tray_state, self.dispatch_tray_action)
        self.refresh_compact_controls()
        self.apply_settings_panel_visibility(initial=True)
        self.root.after(80, self.finish_window_setup)

        try:
            if self.startup_manager.sync_if_needed():
                self.settings_hint_var.set("检测到程序已迁移，开机自启路径已自动更新。")
        except Exception:
            pass

    def finish_window_setup(self) -> None:
        self.hwnd = self.root.winfo_id()
        apply_native_window_style(self.hwnd)
        self.apply_window_alpha()
        self.force_repaint()
        self.tray.start()
        self.tray.refresh_icon()

    def get_tray_state(self) -> dict[str, bool]:
        return {
            "visible": self.is_window_visible,
            "topmost": self.settings["topmost"],
            "startup": self.startup_manager.is_enabled(),
        }

    def dispatch_tray_action(self, action: str) -> None:
        action_map = {
            "show": self.show_window,
            "hide": self.hide_to_tray,
            "topmost": self.toggle_topmost,
            "startup": self.toggle_startup,
            "exit": self.quit_app,
        }
        callback = action_map.get(action)
        if callback:
            self.root.after(0, callback)

    def make_icon_button(
        self,
        parent: tk.Misc,
        text: str,
        command: Any,
        background: str | None = None,
        hover: str | None = None,
        font_family: str | None = None,
    ) -> tk.Label:
        normal_bg = background or THEME["button"]
        hover_bg = hover or THEME["button_hover"]
        button = tk.Label(
            parent,
            text=text,
            bg=normal_bg,
            fg=THEME["text"],
            padx=0,
            pady=0,
            width=3,
            height=1,
            font=((font_family or self.ui_font_family), 10, "bold"),
            cursor="hand2",
            anchor="center",
        )
        button._normal_bg = normal_bg
        button._hover_bg = hover_bg
        button.bind("<Enter>", lambda _event, b=button: b.configure(bg=b._hover_bg))
        button.bind("<Leave>", lambda _event, b=button: b.configure(bg=b._normal_bg))
        button.bind("<Button-1>", lambda _event: command())
        return button

    def make_text_button(
        self,
        parent: tk.Misc,
        text: str | tk.StringVar,
        command: Any,
        width: int = 8,
    ) -> tk.Label:
        button = tk.Label(
            parent,
            text=text if isinstance(text, str) else None,
            textvariable=text if isinstance(text, tk.StringVar) else None,
            bg=THEME["button"],
            fg=THEME["text"],
            padx=12,
            pady=7,
            font=(self.ui_font_family, 9, "bold"),
            cursor="hand2",
            anchor="center",
            width=width,
        )
        button._normal_bg = THEME["button"]
        button._hover_bg = THEME["button_hover"]
        button.bind("<Enter>", lambda _event, b=button: b.configure(bg=b._hover_bg))
        button.bind("<Leave>", lambda _event, b=button: b.configure(bg=b._normal_bg))
        button.bind("<Button-1>", lambda _event: command())
        return button

    def pick_font_family(self, candidates: list[str]) -> str:
        available = set(tkfont.families(self.root))
        for name in candidates:
            if name in available:
                return name
        return "TkDefaultFont"

    def apply_window_alpha(self) -> None:
        target_alpha = self.settings["alpha"]
        self.root.attributes("-alpha", 1.0)
        self.root.after(30, lambda: self.root.attributes("-alpha", target_alpha))
        self.root.after(60, self.force_repaint)

    def force_repaint(self) -> None:
        widgets = [
            self.title_label,
            self.gear_button,
            self.minimize_button,
            self.close_button,
            self.topmost_button,
            self.startup_button,
            self.alpha_down_button,
            self.alpha_up_button,
            self.opacity_label,
            self.settings_hint,
        ]
        for widget in widgets:
            text_value = widget.cget("text")
            if text_value:
                widget.configure(text=text_value)
        self.text_box.update_idletasks()
        self.root.update_idletasks()

    def refresh_compact_controls(self) -> None:
        self.topmost_button_var.set("取消置顶" if self.settings["topmost"] else "设为置顶")
        self.startup_button_var.set("关闭自启" if self.startup_manager.is_enabled() else "开启自启")
        self.opacity_label_var.set(f"透明度 {round(self.settings['alpha'] * 100):d}%")
        if self.settings["settings_expanded"]:
            self.gear_button._normal_bg = THEME["button_hover"]
        else:
            self.gear_button._normal_bg = THEME["button"]
        self.gear_button._hover_bg = THEME["button_hover"]
        self.gear_button.configure(bg=self.gear_button._normal_bg)

    def apply_settings_panel_visibility(self, initial: bool = False) -> None:
        if self.settings["settings_expanded"]:
            self.settings_panel.pack(fill="x", before=self.editor_shell)
        else:
            self.settings_panel.pack_forget()
        self.refresh_compact_controls()
        if not initial:
            self.schedule_save()
            self.force_repaint()

    def toggle_settings_panel(self) -> None:
        self.settings["settings_expanded"] = not self.settings["settings_expanded"]
        self.apply_settings_panel_visibility()

    def start_drag(self, event: tk.Event) -> None:
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + (event.x - self.drag_start_x)
        y = self.root.winfo_y() + (event.y - self.drag_start_y)
        self.root.geometry(f"+{x}+{y}")
        self.schedule_save()

    def stop_drag(self, _event: tk.Event) -> None:
        self.schedule_save()

    def start_resize(self, event: tk.Event) -> None:
        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root
        self.resize_start_width = self.root.winfo_width()
        self.resize_start_height = self.root.winfo_height()

    def on_resize(self, event: tk.Event) -> None:
        delta_x = event.x_root - self.resize_start_x
        delta_y = event.y_root - self.resize_start_y
        new_width = max(380, self.resize_start_width + delta_x)
        new_height = max(300, self.resize_start_height + delta_y)
        self.root.geometry(f"{new_width}x{new_height}")
        self.schedule_save()

    def stop_resize(self, _event: tk.Event) -> None:
        self.schedule_save()

    def on_window_configure(self, _event: tk.Event) -> None:
        if self.is_window_visible and not self.is_exiting:
            self.schedule_save()

    def on_text_changed(self, _event: tk.Event) -> None:
        self.schedule_save()

    def adjust_alpha_down(self) -> None:
        self.adjust_alpha(-0.04)

    def adjust_alpha_up(self) -> None:
        self.adjust_alpha(0.04)

    def adjust_alpha(self, delta: float) -> None:
        self.settings["alpha"] = min(1.0, max(0.72, self.settings["alpha"] + delta))
        self.apply_window_alpha()
        self.refresh_compact_controls()
        self.schedule_save()

    def toggle_topmost(self) -> None:
        self.settings["topmost"] = not self.settings["topmost"]
        self.root.attributes("-topmost", self.settings["topmost"])
        self.refresh_compact_controls()
        self.schedule_save()
        self.tray.refresh_icon()

    def toggle_startup(self) -> None:
        target_state = not self.startup_manager.is_enabled()
        try:
            self.startup_manager.set_enabled(target_state)
        except Exception as exc:
            messagebox.showerror("开机自启失败", f"无法更新开机自启设置：\n{exc}")
            return
        self.refresh_compact_controls()
        self.tray.refresh_icon()

    def hide_to_tray(self) -> None:
        if not self.is_window_visible or self.is_exiting:
            return
        self.persist_settings()
        self.root.withdraw()
        self.is_window_visible = False
        self.tray.refresh_icon()

    def show_window(self) -> None:
        if self.is_exiting:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.settings["topmost"])
        self.is_window_visible = True
        if self.hwnd:
            apply_native_window_style(self.hwnd)
        self.apply_window_alpha()
        self.force_repaint()
        self.tray.refresh_icon()

    def schedule_save(self) -> None:
        if self.save_after_id is not None:
            self.root.after_cancel(self.save_after_id)
        self.save_after_id = self.root.after(250, self.persist_settings)

    def collect_settings(self) -> dict[str, Any]:
        if self.is_window_visible:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
        else:
            width = self.settings["width"]
            height = self.settings["height"]
            x = self.settings["x"]
            y = self.settings["y"]
        return {
            "title": self.settings["title"],
            "width": width,
            "height": height,
            "x": x,
            "y": y,
            "alpha": self.settings["alpha"],
            "topmost": self.settings["topmost"],
            "settings_expanded": self.settings["settings_expanded"],
            "content": self.text_box.get("1.0", "end-1c"),
        }

    def persist_settings(self) -> None:
        self.save_after_id = None
        self.settings = merge_settings(self.collect_settings())
        self.store.save(self.settings)

    def quit_app(self) -> None:
        if self.is_exiting:
            return
        self.is_exiting = True
        if self.save_after_id is not None:
            self.root.after_cancel(self.save_after_id)
            self.save_after_id = None
        self.persist_settings()
        self.tray.stop()
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable Windows floating window.")
    parser.add_argument("--smoke-test", action="store_true", help="Write a runtime report and exit.")
    parser.add_argument("--print-paths", action="store_true", help="Print resolved portable paths and exit.")
    parser.add_argument("--ui-smoke-test", action="store_true", help="Create the window and tray briefly, then exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_dir = get_app_dir()
    store = SettingsStore(app_dir)
    settings = store.load()

    if args.print_paths:
        print(f"app_dir={app_dir}")
        print(f"settings_path={store.settings_path}")
        print(f"runtime_report_path={store.runtime_report_path}")
        return 0

    if args.smoke_test:
        if not store.settings_path.exists():
            store.save(settings)
        report_path = store.write_runtime_report(settings)
        print(report_path)
        return 0

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Unable to create Tk window: {exc}", file=sys.stderr)
        return 1

    app = FloatingWindowApp(root, store)
    if args.ui_smoke_test:
        root.after(900, app.quit_app)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
