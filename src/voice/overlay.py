#!/usr/bin/env python3
"""Floating voice assistant overlay — orb-style (Siri / Gemini aesthetic).

Left panel: state label + subtitle.
Right panel: animated circular orb that changes per state.
Polls /tmp/.ragenie_voice_state.json every 80 ms.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
import tkinter as tk

# ── Constants ─────────────────────────────────────────────────────────────────

STATE_FILE = "/tmp/.ragenie_voice_state.json"
POLL_MS    = 80
ANIM_MS    = 33
STALE_S    = 12

W, H    = 160, 160
ORB_CX  = W // 2       # orb centre x
ORB_CY  = H // 2       # orb centre y
ORB_R   = 68           # orb radius

# Pre-seeded node positions for the UNDERSTANDING network animation
_rng = random.Random(7)
_NODES = [(_rng.uniform(-0.75, 0.75), _rng.uniform(-0.75, 0.75)) for _ in range(12)]

# ── Pill helper ─────────────────────────────────────────────────────────────

def _pill(cv: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
          r: int, fill: str, outline: str = "") -> None:
    """Draw a filled rounded rectangle on a transparent canvas."""
    for sx, sy, s, e in [
        (x1,      y1,      90,  90),
        (x2-2*r,  y1,       0,  90),
        (x1,      y2-2*r, 180,  90),
        (x2-2*r,  y2-2*r, 270,  90),
    ]:
        cv.create_arc(sx, sy, sx+2*r, sy+2*r, start=s, extent=e,
                      style="pieslice", fill=fill, outline=fill)
    cv.create_rectangle(x1+r, y1,   x2-r, y2,   fill=fill, outline=fill)
    cv.create_rectangle(x1,   y1+r, x2,   y2-r, fill=fill, outline=fill)
    if outline:
        cv.create_arc(x1,     y1,     x1+2*r, y1+2*r, start=90,  extent=90,  style="arc", outline=outline)
        cv.create_arc(x2-2*r, y1,     x2,     y1+2*r, start=0,   extent=90,  style="arc", outline=outline)
        cv.create_arc(x1,     y2-2*r, x1+2*r, y2,     start=180, extent=90,  style="arc", outline=outline)
        cv.create_arc(x2-2*r, y2-2*r, x2,     y2,     start=270, extent=90,  style="arc", outline=outline)
        cv.create_line(x1+r, y1, x2-r, y1, fill=outline)
        cv.create_line(x1+r, y2, x2-r, y2, fill=outline)
        cv.create_line(x1, y1+r, x1, y2-r, fill=outline)
        cv.create_line(x2, y1+r, x2, y2-r, fill=outline)


# ── State configuration ───────────────────────────────────────────────────────

STATES: dict[str, dict] = {
    "IDLE": {
        "bg": "#07070F",
        "label": "IDLE",         "label_color": "#33335A",
        "sub":   "Say 'hey jarvis' to begin", "sub_color": "#22223A",
        "orb_bg": "#09091A",     "ring": "#4A4A9A",
        "mode": "idle",          "wc": ["#5555BB", "#3A3A88"],
    },
    "DISCONNECTED": {
        "bg": "#0F0808",
        "label": "DISCONNECTED",  "label_color": "#553333",
        "sub":   "Voice client offline",      "sub_color": "#3A2222",
        "orb_bg": "#0A0505",     "ring": "#552222",
        "mode": "idle",          "wc": ["#662222", "#441515"],
    },
    "LISTENING": {
        "bg": "#050D16",
        "label": "LISTENING",    "label_color": "#00E8D8",
        "sub":   "Capturing your voice…",     "sub_color": "#2A7080",
        "orb_bg": "#030C13",     "ring": "#007A8A",
        "mode": "wave",          "wc": ["#00E5D0", "#00B0BC", "#006870"],
    },
    "TRANSCRIBING": {
        "bg": "#050918",
        "label": "UNDERSTANDING", "label_color": "#44AAFF",
        "sub":   "Analyzing what you said…",  "sub_color": "#234A66",
        "orb_bg": "#03070F",     "ring": "#1C4488",
        "mode": "network",       "wc": ["#66CCFF", "#3388EE", "#1144AA"],
    },
    "WAITING_RESPONSE": {
        "bg": "#0B0516",
        "label": "THINKING",     "label_color": "#CC44FF",
        "sub":   "Finding the best answer…",  "sub_color": "#4A1866",
        "orb_bg": "#07030F",     "ring": "#6A1888",
        "mode": "spiral",        "wc": ["#EE44FF", "#AA22CC", "#661888"],
    },
    "SPEAKING": {
        "bg": "#120706",
        "label": "RESPONDING",   "label_color": "#FF7744",
        "sub":   "Here's what I found…",      "sub_color": "#7A3020",
        "orb_bg": "#0E0403",     "ring": "#992211",
        "mode": "wave",          "wc": ["#FF6644", "#EE3311", "#AA2200"],
    },
    "INTERRUPTED": {
        "bg": "#0F0C00",
        "label": "INTERRUPTED",  "label_color": "#FFCC00",
        "sub":   "Listening for new query…",  "sub_color": "#5A4800",
        "orb_bg": "#0B0900",     "ring": "#776600",
        "mode": "flash",         "wc": ["#FFDD00", "#FFAA00", "#AA7700"],
    },
    "DISCONNECTED": {
        "bg": "#07070F",
        "label": "OFFLINE",      "label_color": "#202038",
        "sub":   "Backend not running",       "sub_color": "#141428",
        "orb_bg": "#05050E",     "ring": "#121228",
        "mode": "idle",          "wc": ["#181828"],
    },
}


# ── Wave animation (LISTENING / SPEAKING) ────────────────────────────────────

def _draw_wave(cv: tk.Canvas, t: float, cfg: dict) -> None:
    """3 overlapping sine waves clipped to the orb circle."""
    wc   = cfg["wc"]
    layers = [
        (ORB_R * 0.52, 3.2, 0.00, wc[0], 3),
        (ORB_R * 0.34, 2.5, 1.30, wc[1] if len(wc) > 1 else wc[0], 2),
        (ORB_R * 0.20, 4.8, 2.60, wc[2] if len(wc) > 2 else wc[0], 2),
    ]
    for amp, spd, phase_off, color, width in layers:
        seg: list[float] = []
        for xo in range(-ORB_R + 4, ORB_R - 3, 2):
            y_wave = ORB_CY + amp * math.sin(spd * t + xo * 0.06 + phase_off)
            dy = y_wave - ORB_CY
            if xo * xo + dy * dy <= ORB_R * ORB_R:
                seg.extend([ORB_CX + xo, y_wave])
            elif len(seg) >= 4:
                cv.create_line(seg, fill=color, width=width,
                               smooth=True, capstyle="round")
                seg = []
        if len(seg) >= 4:
            cv.create_line(seg, fill=color, width=width,
                           smooth=True, capstyle="round")

    # Dotted circle ring
    for deg in range(0, 360, 7):
        rad = math.radians(deg + t * 12)
        px  = ORB_CX + (ORB_R + 1) * math.cos(rad)
        py  = ORB_CY + (ORB_R + 1) * math.sin(rad)
        cv.create_oval(px - 1.5, py - 1.5, px + 1.5, py + 1.5,
                       fill=cfg["ring"], outline="")


# ── Network animation (TRANSCRIBING / UNDERSTANDING) ─────────────────────────

def _draw_network(cv: tk.Canvas, t: float, cfg: dict) -> None:
    """Moving neural-network nodes with connecting lines inside the orb."""
    wc    = cfg["wc"]
    nodes = []
    for i, (nx, ny) in enumerate(_NODES):
        orb  = 0.06
        phase = t * 0.5 + i * 0.72
        px = ORB_CX + (nx + orb * math.cos(phase)) * ORB_R
        py = ORB_CY + (ny + orb * math.sin(phase)) * ORB_R
        nodes.append((px, py))

    # Edges
    link_d = ORB_R * 0.8
    for i, (x1, y1) in enumerate(nodes):
        for j, (x2, y2) in enumerate(nodes):
            if j <= i:
                continue
            d = math.hypot(x2 - x1, y2 - y1)
            if d < link_d:
                bright = max(0.15, 1.0 - d / link_d)
                r = int(0x33 * bright); g = int(0x88 * bright); b = int(0xFF * bright)
                cv.create_line(x1, y1, x2, y2,
                               fill=f"#{r:02x}{g:02x}{b:02x}", width=1)

    # Node dots + glow
    for px, py in nodes:
        cv.create_oval(px-5, py-5, px+5, py+5, fill=wc[0], outline="")
        cv.create_oval(px-8, py-8, px+8, py+8,
                       fill="", outline=wc[1] if len(wc) > 1 else wc[0], width=1)

    # Thin circle ring
    cv.create_oval(ORB_CX - ORB_R, ORB_CY - ORB_R,
                   ORB_CX + ORB_R, ORB_CY + ORB_R,
                   outline=cfg["ring"], width=1)


# ── Spiral animation (WAITING_RESPONSE / THINKING) ───────────────────────────

def _draw_spiral(cv: tk.Canvas, t: float, cfg: dict) -> None:
    """Rotating galaxy-like spiral arms inside the orb."""
    wc       = cfg["wc"]
    rotation = t * 1.4   # rad/s

    for arm in range(3):
        arm_offset = (2 * math.pi / 3) * arm
        pts: list[float] = []
        for step in range(0, 300, 4):
            theta = (step / 300.0) * 4 * math.pi
            r     = (step / 300.0) * ORB_R * 0.90
            angle = theta + rotation + arm_offset
            x = ORB_CX + r * math.cos(angle)
            y = ORB_CY + r * math.sin(angle)
            if (x - ORB_CX) ** 2 + (y - ORB_CY) ** 2 <= ORB_R * ORB_R:
                pts.extend([x, y])
        if len(pts) >= 4:
            color = wc[arm % len(wc)]
            cv.create_line(pts, fill=color, width=2,
                           smooth=True, capstyle="round")

    # Scattered bright dots along spiral paths
    for i in range(18):
        angle = (i / 18.0) * 4 * math.pi + rotation
        r     = (i / 18.0) * ORB_R * 0.88
        x = ORB_CX + r * math.cos(angle)
        y = ORB_CY + r * math.sin(angle)
        dr = 3 if i % 4 == 0 else 1.5
        cv.create_oval(x - dr, y - dr, x + dr, y + dr,
                       fill=wc[0], outline="")

    # Glowing ring
    cv.create_oval(ORB_CX - ORB_R, ORB_CY - ORB_R,
                   ORB_CX + ORB_R, ORB_CY + ORB_R,
                   outline=cfg["ring"], width=2)


# ── Idle pulse ────────────────────────────────────────────────────────────────

def _draw_idle(cv: tk.Canvas, t: float, cfg: dict) -> None:
    pulse = 0.55 + 0.45 * math.sin(t * 1.0)
    r1    = int(ORB_R * 0.40 * pulse)
    r2    = int(ORB_R * 0.65 * pulse)
    # Outer glow ring (subtle halo)
    cv.create_oval(ORB_CX - ORB_R - 4, ORB_CY - ORB_R - 4,
                   ORB_CX + ORB_R + 4, ORB_CY + ORB_R + 4,
                   outline=cfg["ring"], width=1, dash=(2, 8))
    cv.create_oval(ORB_CX - r2, ORB_CY - r2, ORB_CX + r2, ORB_CY + r2,
                   outline=cfg["ring"], width=2)
    cv.create_oval(ORB_CX - r1, ORB_CY - r1, ORB_CX + r1, ORB_CY + r1,
                   fill=cfg["wc"][0], outline="")
    cv.create_oval(ORB_CX - ORB_R, ORB_CY - ORB_R,
                   ORB_CX + ORB_R, ORB_CY + ORB_R,
                   outline=cfg["ring"], width=2, dash=(4, 5))


# ── Flash (INTERRUPTED) ───────────────────────────────────────────────────────

def _draw_flash(cv: tk.Canvas, t: float, cfg: dict) -> None:
    wc  = cfg["wc"]
    vis = math.sin(t * 7) > 0
    _draw_wave(cv, t, cfg)   # reuse wave with flash colours
    if vis:
        cv.create_oval(ORB_CX - ORB_R, ORB_CY - ORB_R,
                       ORB_CX + ORB_R, ORB_CY + ORB_R,
                       outline=wc[0], width=2)


# ── ORB dispatcher ────────────────────────────────────────────────────────────

_DRAW_FN = {
    "wave":    _draw_wave,
    "network": _draw_network,
    "spiral":  _draw_spiral,
    "idle":    _draw_idle,
    "flash":   _draw_flash,
}

def _draw_orb(cv: tk.Canvas, t: float, cfg: dict) -> None:
    """Dispatch animation — no background fill; window is fully transparent."""
    fn = _DRAW_FN.get(cfg["mode"], _draw_idle)
    fn(cv, t, cfg)


# ── Main overlay class ────────────────────────────────────────────────────────

class VoiceOverlay:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # ── Full transparency (macOS native) ──────────────────────────────────
        # The window itself is transparent; only drawn shapes are visible,
        # creating the floating Siri/Gemini effect.
        try:
            self.root.wm_attributes("-transparent", True)
            self.root.configure(bg="systemTransparent")
            self._transparent = True
        except Exception:
            self.root.configure(bg="#07070F")
            self.root.attributes("-alpha", 0.93)
            self._transparent = False

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - W) // 2
        y  = sh - H - 100
        self.root.geometry(f"{W}x{H}+{x}+{y}")

        _cv_bg = "systemTransparent" if self._transparent else "#07070F"
        self.cv = tk.Canvas(self.root, width=W, height=H,
                            highlightthickness=0, bd=0, bg=_cv_bg)
        self.cv.pack()
        self.root.lift()
        self.root.after(120, self.root.lift)

        self.cv.bind("<ButtonPress-1>", self._drag_start)
        self.cv.bind("<B1-Motion>",     self._drag_move)
        self._drag_ox = self._drag_oy = 0

        self._state      = "IDLE"
        self._user_text  = ""
        self._agent_text = ""
        self._tool       = ""
        self._last_ts    = 0.0
        self._t          = 0.0

        self._start_poll()
        self._start_anim()

    # ── Polling ───────────────────────────────────────────────────────────────

    def _start_poll(self) -> None:
        self._poll()
        self.root.after(POLL_MS, self._start_poll)

    def _poll(self) -> None:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as fh:
                    data = json.load(fh)
                ts = data.get("ts", 0.0)
                if ts != self._last_ts:
                    self._last_ts    = ts
                    self._state      = data.get("state", "IDLE")
                    self._user_text  = data.get("user_text",  "")
                    self._agent_text = data.get("agent_text", "")
                    self._tool       = data.get("tool", "")
                    if self._state == "SHUTDOWN":
                        self.root.after(900, self.root.destroy)
                if time.time() - self._last_ts > STALE_S:
                    self._state = "DISCONNECTED"
        except Exception:
            pass

    # ── Animation ─────────────────────────────────────────────────────────────

    def _start_anim(self) -> None:
        self._t += ANIM_MS / 1000.0
        self._draw()
        self.root.after(ANIM_MS, self._start_anim)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        cv  = self.cv
        t   = self._t
        cfg = STATES.get(self._state, STATES["IDLE"])

        cv.delete("all")

        # Pure orb — no text, no background rect.
        # Only the circle drawn by _draw_orb is visible on the transparent window.
        _draw_orb(cv, t, cfg)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _drag_start(self, e: tk.Event) -> None:
        self._drag_ox = e.x_root - self.root.winfo_x()
        self._drag_oy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e: tk.Event) -> None:
        self.root.geometry(
            f"+{e.x_root - self._drag_ox}+{e.y_root - self._drag_oy}")

    def run(self) -> None:
        self.root.mainloop()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trunc(s: str, n: int) -> str:
    return s[:n] + "…" if len(s) > n else s


if __name__ == "__main__":
    VoiceOverlay().run()
