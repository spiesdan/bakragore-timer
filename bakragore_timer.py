import tkinter as tk
import ctypes
import time
import winsound
import os
import sys
import json

TP_INTERVAL = 90
STRIKE_INTERVAL = 12
COUNTDOWN_START = 5

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_COLORKEY = 0x00000001

TRANSPARENT_COLOR = "#010101"

STONE_BG = "#2b2b2b"
STONE_MID = "#383838"
STONE_DARK = "#1e1e1e"
STONE_LIGHT = "#454545"
GOLD = "#c9a84c"
GOLD_DARK = "#8b6914"
ORANGE = "#ff7700"
RED = "#ff2222"
RED_DARK = "#990000"
GREEN = "#2d8a2d"
GREEN_DARK = "#1a5a1a"
TEXT = "#e8d8a8"
TEXT_DIM = "#a89878"
TEXT_BRIGHT = "#f0e0b8"

BOSSES = ["Bakragore", "Chagorz", "Vemiath"]
WORDS = {5: "CINCO", 4: "QUATRO", 3: "TRÊS", 2: "DOIS", 1: "UM"}
ESCALA = 0.7


def P(v):
    return max(1, int(round(v * ESCALA)))


def format_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_app_dir(), "config.json")
DEFAULT_HOTKEY = {"vk": 0x77, "ctrl": True, "alt": False, "shift": False, "display": "Ctrl+F8"}
MODIFIER_KEYSYMS = {
    "Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Super_L", "Super_R", "Win_L", "Win_R",
    "Caps_Lock", "Num_Lock", "Scroll_Lock",
}


def falar_numero(n):
    try:
        path = os.path.join(AUDIO_DIR, f"{n}.wav")
        if os.path.exists(path):
            winsound.PlaySound(
                path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
    except Exception:
        pass


class TibiaButton(tk.Frame):
    def __init__(self, parent, text, command, bg, bg_dark, icon="", **kwargs):
        super().__init__(parent, **kwargs)
        self.command = command
        self.bg = bg
        self.bg_dark = bg_dark

        self.config(bg=GOLD_DARK, padx=P(2), pady=P(2))
        self.inner = tk.Frame(self, bg=bg, padx=P(8), pady=P(6))
        self.inner.pack(fill="both", expand=True)
        self.inner.bind("<Enter>", self._on_enter)
        self.inner.bind("<Leave>", self._on_leave)
        self.inner.bind("<Button-1>", self._on_click)

        if icon:
            self.icon_label = tk.Label(self.inner, text=icon, bg=bg, fg=TEXT, font=("Segoe UI", 14))
            self.icon_label.pack(side="left", padx=(0, P(6)))
            self.icon_label.bind("<Enter>", self._on_enter)
            self.icon_label.bind("<Leave>", self._on_leave)
            self.icon_label.bind("<Button-1>", self._on_click)

        self.text_label = tk.Label(self.inner, text=text, bg=bg, fg=TEXT, font=("Consolas", 11, "bold"))
        self.text_label.pack(side="left")
        self.text_label.bind("<Enter>", self._on_enter)
        self.text_label.bind("<Leave>", self._on_leave)
        self.text_label.bind("<Button-1>", self._on_click)

    def _on_enter(self, event):
        self.inner.config(bg=self.bg_dark)
        for w in self.inner.winfo_children():
            w.config(bg=self.bg_dark)

    def _on_leave(self, event):
        self.inner.config(bg=self.bg)
        for w in self.inner.winfo_children():
            w.config(bg=self.bg)

    def _on_click(self, event):
        if self.command:
            self.command()


class OverlayApp:
    def __init__(self, root):
        self.root = root
        self.boss_index = 0
        self.tp_running = False
        self.tp_start_time = 0
        self.strike_running = False
        self.strike_start_time = 0
        self.last_countdown = None
        self.last_tp_countdown = None
        self.drag_data = {"x": 0, "y": 0}
        self.click_through = True
        self.paused = False
        self.pause_start = 0.0
        self.icon_photo = None
        self.hotkey = self._load_hotkey()
        self.recording = False
        self.hotkey_armed = True
        self._hk_prev = False

        self._setup_window()
        self._load_icon()
        self._build_ui()
        self._auto_size()
        self._set_click_through(True)
        self.root.after(50, self._tick)
        self.root.after(100, self._poll_hotkey)

    def _setup_window(self):
        self.root.title("Bakragore Timer")
        try:
            atual = self.root.tk.call("tk", "scaling")
            self.root.tk.call("tk", "scaling", atual * ESCALA)
        except Exception:
            pass
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.geometry("340x440+100+100")
        self.root.update_idletasks()
        self.root.bind("<Map>", self._on_map)

    def _auto_size(self):
        self.root.update_idletasks()
        w = max(self.root.winfo_reqwidth(), 200)
        h = self.root.winfo_reqheight()
        self.root.geometry(f"{w}x{h}+100+100")
        self.root.update_idletasks()

    def _load_icon(self):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "icone.png")
            if os.path.exists(path):
                foto = tk.PhotoImage(file=path)
                self.icon_photo = foto.zoom(7, 7).subsample(10, 10)
                self.root.iconphoto(False, self.icon_photo)
        except Exception:
            self.icon_photo = None

    def _set_click_through(self, enabled):
        hwnd = self.root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        ctypes.windll.user32.SetLayeredWindowAttributes(
            hwnd, int(TRANSPARENT_COLOR[1:], 16), 0, LWA_COLORKEY
        )
        self.click_through = enabled

    def _is_mouse_over_widget(self, widget):
        try:
            mx = self.root.winfo_pointerx()
            my = self.root.winfo_pointery()
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            ww = widget.winfo_width()
            wh = widget.winfo_height()
            return wx <= mx <= wx + ww and wy <= my <= wy + wh
        except Exception:
            return False

    def _any_button_hovered(self):
        for w in [self.tp_btn, self.strike_btn, self.boss_btn, self.reset_btn,
                  self.pause_btn, self.min_btn, self.close_btn]:
            if self._is_mouse_over_widget(w):
                return True
        return False

    def _build_ui(self):
        self.title_bar = tk.Frame(self.root, bg=STONE_DARK, height=P(24))
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)
        self.title_bar.bind("<Button-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._on_drag)

        title_text = tk.Label(self.title_bar, text="  Bakragore Timer", bg=STONE_DARK, fg=TEXT_DIM,
                              font=("Consolas", 8))
        title_text.pack(side="left", padx=(4, 0))
        title_text.bind("<Button-1>", self._start_drag)
        title_text.bind("<B1-Motion>", self._on_drag)

        self.close_btn = tk.Label(self.title_bar, text="✕", bg=STONE_DARK, fg=TEXT_DIM, font=("Consolas", 10), cursor="hand2")
        self.close_btn.pack(side="right", padx=(0, 4))
        self.close_btn.bind("<Button-1>", lambda e: self.root.destroy())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg="#8b0000", fg="#ffffff"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg=STONE_DARK, fg=TEXT_DIM))

        self.min_btn = tk.Label(self.title_bar, text="─", bg=STONE_DARK, fg=TEXT_DIM, font=("Consolas", 10), cursor="hand2")
        self.min_btn.pack(side="right", padx=(0, 2))
        self.min_btn.bind("<Button-1>", self._minimize)

        self.main_frame = tk.Frame(self.root, bg=STONE_DARK, padx=P(3), pady=P(3))
        self.main_frame.pack(fill="both", expand=True, padx=P(2), pady=(0, P(2)))
        self.main_frame.bind("<Button-1>", self._start_drag)
        self.main_frame.bind("<B1-Motion>", self._on_drag)

        self.content = tk.Frame(self.main_frame, bg=STONE_BG)
        self.content.pack(fill="both", expand=True)
        self.content.bind("<Button-1>", self._start_drag)
        self.content.bind("<B1-Motion>", self._on_drag)

        self._build_header()
        self._build_tp_section()
        self._build_strike_section()
        self._build_footer()

    def _build_header(self):
        header = tk.Frame(self.content, bg=STONE_MID, padx=P(8), pady=P(6))
        header.pack(fill="x", padx=P(4), pady=(P(4), 0))
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)

        icon_frame = tk.Frame(header, bg=STONE_DARK, padx=P(2), pady=P(2))
        icon_frame.pack(side="left")
        if self.icon_photo is not None:
            tk.Label(icon_frame, image=self.icon_photo, bg=STONE_DARK).pack()
        else:
            tk.Label(icon_frame, text="\U0001F392", bg=STONE_DARK, fg=TEXT,
                     font=("Segoe UI", 16)).pack()

        name_frame = tk.Frame(header, bg=STONE_MID)
        name_frame.pack(side="left", fill="x", expand=True, padx=(P(8), 0))
        name_frame.bind("<Button-1>", self._start_drag)
        name_frame.bind("<B1-Motion>", self._on_drag)

        self.boss_label = tk.Label(name_frame, text=BOSSES[self.boss_index], bg=STONE_MID, fg=TEXT_BRIGHT,
                                  font=("Consolas", 14, "bold"), anchor="w")
        self.boss_label.pack(fill="x")
        self.boss_label.bind("<Button-1>", self._start_drag)
        self.boss_label.bind("<B1-Motion>", self._on_drag)

        self.boss_btn = TibiaButton(header, "Trocar", self._cycle_boss, STONE_DARK, STONE_LIGHT, icon="🔀")
        self.boss_btn.pack(side="right")

    def _build_tp_section(self):
        tp_frame = tk.Frame(self.content, bg=STONE_BG, padx=P(12), pady=P(8))
        tp_frame.pack(fill="x", padx=P(4))
        tp_frame.bind("<Button-1>", self._start_drag)
        tp_frame.bind("<B1-Motion>", self._on_drag)

        tk.Label(tp_frame, text="PRÓXIMO TP", bg=STONE_BG, fg=TEXT,
                 font=("Consolas", 11, "bold")).pack(anchor="w")
        tp_frame.winfo_children()[-1].bind("<Button-1>", self._start_drag)
        tp_frame.winfo_children()[-1].bind("<B1-Motion>", self._on_drag)

        self.tp_time_label = tk.Label(tp_frame, text="--:--", bg=STONE_BG, fg=ORANGE,
                                      font=("Consolas", 36, "bold"))
        self.tp_time_label.pack(pady=(P(8), P(4)))

        self.tp_status = tk.Label(tp_frame, text="Aguardando início...", bg=STONE_BG, fg=TEXT_DIM,
                                  font=("Consolas", 9))
        self.tp_status.pack(anchor="w")

        divider = tk.Frame(self.content, bg=GOLD_DARK, height=2)
        divider.pack(fill="x", padx=P(8), pady=P(2))

    def _build_strike_section(self):
        strike_frame = tk.Frame(self.content, bg=STONE_BG, padx=P(12), pady=P(8))
        strike_frame.pack(fill="x", padx=P(4))
        strike_frame.bind("<Button-1>", self._start_drag)
        strike_frame.bind("<B1-Motion>", self._on_drag)

        tk.Label(strike_frame, text="12 SEGUNDOS", bg=STONE_BG, fg=TEXT,
                 font=("Consolas", 11, "bold")).pack(anchor="w")
        strike_frame.winfo_children()[-1].bind("<Button-1>", self._start_drag)
        strike_frame.winfo_children()[-1].bind("<B1-Motion>", self._on_drag)

        self.strike_time_label = tk.Label(strike_frame, text="--", bg=STONE_BG, fg=RED,
                                          font=("Consolas", 36, "bold"))
        self.strike_time_label.pack(pady=(P(8), P(4)), anchor="w")

        self.countdown_label = tk.Label(strike_frame, text="", bg=STONE_BG, fg="#ffee00",
                                        font=("Consolas", 20, "bold"))
        self.countdown_label.pack(anchor="w")

    def _build_footer(self):
        footer = tk.Frame(self.content, bg=STONE_BG, padx=P(8))
        footer.pack(fill="x", padx=P(4), pady=(P(8), P(4)))

        row1 = tk.Frame(footer, bg=STONE_BG)
        row1.pack(fill="x")

        self.tp_btn = TibiaButton(row1, "Entrei na Sala", self._toggle_tp, GREEN_DARK, GREEN, icon="⚔️")
        self.tp_btn.pack(side="left", expand=True, fill="x", padx=(0, P(4)))

        self.strike_btn = TibiaButton(row1, "Mob no TP!", self._start_strike, RED_DARK, RED, icon="👹")
        self.strike_btn.pack(side="left", expand=True, fill="x", padx=(P(4), 0))

        row2 = tk.Frame(footer, bg=STONE_BG)
        row2.pack(fill="x", pady=(P(6), 0))

        self.pause_btn = TibiaButton(row2, "Pausa", self._toggle_pause, STONE_DARK, STONE_LIGHT, icon="⏸")
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=(0, P(4)))

        self.reset_btn = TibiaButton(row2, "Resetar", self._reset_all, STONE_DARK, STONE_LIGHT, icon="🔄")
        self.reset_btn.pack(side="left", expand=True, fill="x", padx=(P(4), 0))

        row3 = tk.Frame(footer, bg=STONE_BG)
        row3.pack(fill="x", pady=(P(6), 0))

        self.hotkey_btn = TibiaButton(
            row3, f"Hotkey: {self.hotkey['display']}", self._record_hotkey, STONE_DARK, STONE_LIGHT, icon="⌨"
        )
        self.hotkey_btn.pack(fill="x")

    def _cycle_boss(self):
        self.boss_index = (self.boss_index + 1) % len(BOSSES)
        self.boss_label.config(text=BOSSES[self.boss_index])

    def _load_hotkey(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                hk = data.get("hotkey")
                if hk and hk.get("vk"):
                    return hk
        except Exception:
            pass
        return dict(DEFAULT_HOTKEY)

    def _save_hotkey(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"hotkey": self.hotkey}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _record_hotkey(self):
        if self.recording:
            return
        self.recording = True
        self.hotkey_armed = False
        self.hotkey_btn.text_label.config(text="Pressione a tecla...", fg=GOLD)
        self.root.focus_force()
        self.root.bind_all("<KeyPress>", self._on_record_key)

    def _on_record_key(self, event):
        if event.keysym == "Escape":
            self.recording = False
            self.hotkey_btn.text_label.config(text=f"Hotkey: {self.hotkey['display']}", fg=TEXT)
            self.root.unbind_all("<KeyPress>")
            return
        if event.keysym in MODIFIER_KEYSYMS or event.keycode == 0:
            return
        ctrl = bool(event.state & 0x0004)
        alt = bool(event.state & 0x0008)
        shift = bool(event.state & 0x0001)
        name = event.keysym
        if len(name) == 1:
            name = name.upper()
        parts = []
        if ctrl:
            parts.append("Ctrl")
        if alt:
            parts.append("Alt")
        if shift:
            parts.append("Shift")
        parts.append(name)
        self.hotkey = {
            "vk": int(event.keycode),
            "ctrl": ctrl,
            "alt": alt,
            "shift": shift,
            "display": "+".join(parts),
        }
        self.recording = False
        self._save_hotkey()
        self.hotkey_btn.text_label.config(text=f"Hotkey: {self.hotkey['display']}", fg=TEXT)
        self.root.unbind_all("<KeyPress>")

    def _poll_hotkey(self):
        try:
            hk = self.hotkey
            user32 = ctypes.windll.user32
            down_vk = bool(user32.GetAsyncKeyState(hk["vk"]) & 0x8000)
            down_ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
            down_alt = bool(user32.GetAsyncKeyState(0x12) & 0x8000)
            down_shift = bool(user32.GetAsyncKeyState(0x10) & 0x8000)
            if not self.hotkey_armed:
                if not (down_vk or down_ctrl or down_alt or down_shift):
                    self.hotkey_armed = True
                self._hk_prev = False
            else:
                combo = (
                    down_vk
                    and down_ctrl == hk["ctrl"]
                    and down_alt == hk["alt"]
                    and down_shift == hk["shift"]
                )
                if combo and not self._hk_prev and not self.recording:
                    self._start_strike()
                self._hk_prev = combo
        except Exception:
            pass
        self.root.after(30, self._poll_hotkey)

    def _toggle_tp(self):
        if self.paused:
            return
        if self.tp_running:
            self.tp_running = False
            self.tp_status.config(text="Timer pausado", fg=TEXT_DIM)
            self.tp_time_label.config(text="--:--")
        else:
            self.tp_running = True
            self.tp_start_time = time.time()
            self.last_tp_countdown = None
            self.tp_status.config(text="TP a cada 1:30", fg=TEXT_BRIGHT)
            self._beep(880, 100)

    def _start_strike(self):
        if not self.tp_running or self.paused:
            return
        self.strike_running = True
        self.strike_start_time = time.time()
        self.last_countdown = None

    def _toggle_pause(self):
        if not self.paused:
            if not (self.tp_running or self.strike_running):
                return
            self.paused = True
            self.pause_start = time.time()
            self.pause_btn.text_label.config(text="Retomar")
            self.tp_status.config(text="PAUSADO", fg="#ffee00")
        else:
            self.paused = False
            delta = time.time() - self.pause_start
            self.tp_start_time += delta
            self.strike_start_time += delta
            self.pause_btn.text_label.config(text="Pausa")
            if self.tp_running:
                self.tp_status.config(text="TP a cada 1:30", fg=TEXT_BRIGHT)

    def _reset_all(self):
        self.tp_running = False
        self.strike_running = False
        self.paused = False
        self.last_countdown = None
        self.last_tp_countdown = None
        self.pause_btn.text_label.config(text="Pausa")
        self.tp_time_label.config(text="--:--")
        self.tp_status.config(text="Aguardando início...", fg=TEXT_DIM)
        self.strike_time_label.config(text="--")
        self.countdown_label.config(text="")

    def _tick(self):
        now = time.time()

        over_btn = self._any_button_hovered()
        if over_btn and self.click_through:
            self._set_click_through(False)
        elif not over_btn and not self.click_through:
            self._set_click_through(True)

        if self.tp_running and not self.paused:
            elapsed = now - self.tp_start_time
            remaining = TP_INTERVAL - (elapsed % TP_INTERVAL)
            self.tp_time_label.config(text=format_time(remaining))

            if remaining <= 5:
                n = min(COUNTDOWN_START, int(remaining) + 1)
                if n != self.last_tp_countdown and n >= 1:
                    self.last_tp_countdown = n
                    falar_numero(n)
            else:
                self.last_tp_countdown = None

            prev_elapsed = elapsed - 0.05
            prev_remaining = TP_INTERVAL - (prev_elapsed % TP_INTERVAL)
            if remaining > prev_remaining and remaining <= TP_INTERVAL:
                self._beep(1200, 150)
                self.tp_status.config(text="TP NASCEU! Passe o mob!", fg="#00ff00")

        if self.strike_running and not self.paused:
            elapsed = now - self.strike_start_time
            remaining = STRIKE_INTERVAL - elapsed

            if remaining <= 0:
                self.strike_running = False
                self.strike_time_label.config(text="0")
                self.countdown_label.config(text="", fg="#ff0000")
                self._beep(200, 600)
            else:
                self.strike_time_label.config(text=str(int(remaining) + 1))

                if remaining <= COUNTDOWN_START:
                    n = min(COUNTDOWN_START, int(remaining) + 1)
                    if n != self.last_countdown and n >= 1:
                        self.last_countdown = n
                        self.countdown_label.config(text=WORDS.get(n, str(n)))
                        falar_numero(n)
                else:
                    self.countdown_label.config(text="")
                    self.last_countdown = None

        self.root.after(50, self._tick)

    def _beep(self, freq, duration):
        try:
            winsound.Beep(freq, duration)
        except Exception:
            pass

    def _minimize(self, event=None):
        self.root.overrideredirect(False)
        self.root.update_idletasks()
        self.root.iconify()

    def _on_map(self, event):
        try:
            if self.root.state() == "normal":
                self.root.overrideredirect(True)
                self.root.wm_attributes("-topmost", True)
                self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
                self._set_click_through(self.click_through)
        except Exception:
            pass

    def _start_drag(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_data["x"]
        y = self.root.winfo_y() + event.y - self.drag_data["y"]
        self.root.geometry(f"+{x}+{y}")


def main():
    root = tk.Tk()
    OverlayApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
