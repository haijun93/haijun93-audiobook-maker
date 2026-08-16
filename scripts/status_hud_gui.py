#!/usr/bin/env python3
"""
Always-On-Top Floating Status HUD for Audiobook Maker
실시간으로 진행상황(http://127.0.0.1:7870)을 화면 맨 위에 항상 띄워주는 플로팅 대시보드 GUI
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import urllib.request
import webbrowser


API_URL = "http://127.0.0.1:7870/api/runtime"
WEB_URL = "http://127.0.0.1:7870/"


class StatusHudApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Audiobook Studio - 실시간 작업 현황 (Always on Top)")
        self.root.geometry("480x560+50+50")
        self.root.minsize(420, 400)
        
        # Always on top
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#121316")
        
        self.is_topmost = True
        self.cards = {}
        self.running = True
        
        self._setup_style()
        self._build_ui()
        
        # Start update thread
        self.update_thread = threading.Thread(target=self._data_fetch_loop, daemon=True)
        self.update_thread.start()

    def _setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Configure dark theme styles
        self.style.configure("TProgressbar",
                             thickness=8,
                             troughcolor="#1e2026",
                             background="#10b981",
                             bordercolor="#1e2026",
                             lightcolor="#10b981",
                             darkcolor="#10b981")
        
        self.style.configure("Degraded.Horizontal.TProgressbar",
                             thickness=8,
                             troughcolor="#1e2026",
                             background="#f59e0b",
                             bordercolor="#1e2026",
                             lightcolor="#f59e0b",
                             darkcolor="#f59e0b")

    def _build_ui(self):
        # Header Frame
        header = tk.Frame(self.root, bg="#1a1c23", pady=10, padx=14)
        header.pack(fill="x", side="top")
        
        title_lbl = tk.Label(header, text="🎧 번역 및 오디오북 실시간 현황",
                             font=("SF Pro Display", 13, "bold"),
                             fg="#f3f4f6", bg="#1a1c23")
        title_lbl.pack(side="left")
        
        # Header Controls
        btn_frame = tk.Frame(header, bg="#1a1c23")
        btn_frame.pack(side="right")
        
        self.pin_btn = tk.Button(btn_frame, text="📌 항상위: ON",
                                 font=("SF Pro Text", 9),
                                 fg="#10b981", bg="#262933",
                                 activebackground="#374151", activeforeground="#ffffff",
                                 relief="flat", padx=6, pady=2,
                                 command=self._toggle_topmost)
        self.pin_btn.pack(side="left", padx=4)
        
        web_btn = tk.Button(btn_frame, text="🌐 웹 대시보드",
                            font=("SF Pro Text", 9),
                            fg="#60a5fa", bg="#262933",
                            activebackground="#374151", activeforeground="#ffffff",
                            relief="flat", padx=6, pady=2,
                            command=lambda: webbrowser.open(WEB_URL))
        web_btn.pack(side="left")
        
        # Container for scrollable cards
        self.cards_frame = tk.Frame(self.root, bg="#121316", padx=12, pady=10)
        self.cards_frame.pack(fill="both", expand=True)
        
        # Summary bar at bottom
        self.footer = tk.Frame(self.root, bg="#1a1c23", pady=6, padx=12)
        self.footer.pack(fill="x", side="bottom")
        
        self.status_lbl = tk.Label(self.footer, text="⚡ 런타임 연결 중...",
                                   font=("SF Pro Text", 9),
                                   fg="#9ca3af", bg="#1a1c23")
        self.status_lbl.pack(side="left")
        
        self.time_lbl = tk.Label(self.footer, text="",
                                 font=("SF Pro Text", 9),
                                 fg="#6b7280", bg="#1a1c23")
        self.time_lbl.pack(side="right")

    def _toggle_topmost(self):
        self.is_topmost = not self.is_topmost
        self.root.attributes("-topmost", self.is_topmost)
        if self.is_topmost:
            self.pin_btn.config(text="📌 항상위: ON", fg="#10b981")
        else:
            self.pin_btn.config(text="📌 항상위: OFF", fg="#9ca3af")

    def _data_fetch_loop(self):
        while self.running:
            try:
                req = urllib.request.Request(API_URL, headers={"User-Agent": "StatusHUD/1.0"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.root.after(0, self._update_ui_data, data)
            except Exception as exc:
                self.root.after(0, self._set_connection_error, str(exc))
            time.sleep(1.0)

    def _set_connection_error(self, err_msg: str):
        self.status_lbl.config(text="⚠️ 런타임 API 응답 대기 중...", fg="#ef4444")
        self.time_lbl.config(text=time.strftime("%H:%M:%S"))

    def _update_ui_data(self, data: dict):
        workflows = data.get("workflows", [])
        self.status_lbl.config(text=f"🟢 {len(workflows)}개 작업 활발히 진행 중", fg="#10b981")
        self.time_lbl.config(text=time.strftime("%H:%M:%S"))
        
        # Update or create card for each workflow
        current_titles = set()
        for idx, wf in enumerate(workflows):
            title = wf.get("title", f"작업 {idx+1}")
            current_titles.add(title)
            
            if title not in self.cards:
                self.cards[title] = self._create_card(title)
                
            self._update_card(self.cards[title], wf)
            
        # Remove old cards
        for title in list(self.cards.keys()):
            if title not in current_titles:
                self.cards[title]["frame"].destroy()
                del self.cards[title]

    def _create_card(self, title: str) -> dict:
        card = tk.Frame(self.cards_frame, bg="#1e2028", bd=0, padx=12, pady=10, relief="flat")
        card.pack(fill="x", pady=6)
        
        # Row 1: Title & Provider Badge
        r1 = tk.Frame(card, bg="#1e2028")
        r1.pack(fill="x")
        
        provider_badge = tk.Label(r1, text="GEMINI", font=("SF Pro Text", 8, "bold"),
                                  fg="#60a5fa", bg="#1e293b", padx=5, pady=1)
        provider_badge.pack(side="left", padx=(0, 6))
        
        title_lbl = tk.Label(r1, text=title, font=("SF Pro Text", 10, "bold"),
                             fg="#f9fafb", bg="#1e2028", anchor="w")
        title_lbl.pack(side="left", fill="x", expand=True)
        
        status_badge = tk.Label(r1, text="RUNNING", font=("SF Pro Text", 8, "bold"),
                                fg="#10b981", bg="#064e3b", padx=5, pady=1)
        status_badge.pack(side="right")
        
        # Row 2: Progress Bar
        r2 = tk.Frame(card, bg="#1e2028", pady=6)
        r2.pack(fill="x")
        
        pbar = ttk.Progressbar(r2, style="TProgressbar", orient="horizontal", mode="determinate")
        pbar.pack(fill="x")
        
        # Row 3: Progress text & Speed / ETA
        r3 = tk.Frame(card, bg="#1e2028")
        r3.pack(fill="x")
        
        prog_lbl = tk.Label(r3, text="0/0 (0%)", font=("SF Pro Text", 9),
                            fg="#d1d5db", bg="#1e2028")
        prog_lbl.pack(side="left")
        
        speed_lbl = tk.Label(r3, text="-- chunks/h", font=("SF Pro Text", 9),
                             fg="#9ca3af", bg="#1e2028")
        speed_lbl.pack(side="right")
        
        # Row 4: Stage & Sub-chunk info
        r4 = tk.Frame(card, bg="#1e2028", pady=2)
        r4.pack(fill="x")
        
        stage_lbl = tk.Label(r4, text="대기 중...", font=("SF Pro Text", 8),
                             fg="#6b7280", bg="#1e2028", anchor="w")
        stage_lbl.pack(side="left", fill="x", expand=True)
        
        return {
            "frame": card,
            "provider_badge": provider_badge,
            "title_lbl": title_lbl,
            "status_badge": status_badge,
            "pbar": pbar,
            "prog_lbl": prog_lbl,
            "speed_lbl": speed_lbl,
            "stage_lbl": stage_lbl,
        }

    def _update_card(self, widgets: dict, wf: dict):
        provider = wf.get("provider", "gemini").upper()
        health = wf.get("health", "healthy")
        status = wf.get("status", "running").upper()
        prog = wf.get("progress", {})
        
        # Provider styling
        if provider == "CHATGPT":
            widgets["provider_badge"].config(text="CHATGPT", fg="#34d399", bg="#064e3b")
        else:
            widgets["provider_badge"].config(text="GEMINI", fg="#60a5fa", bg="#1e3a8a")
            
        # Status styling
        if health == "degraded" or status == "RECOVERING":
            widgets["status_badge"].config(text="복구재시도", fg="#fbbf24", bg="#78350f")
            widgets["pbar"].config(style="Degraded.Horizontal.TProgressbar")
        elif health == "failed":
            widgets["status_badge"].config(text="오류", fg="#f87171", bg="#7f1d1d")
        else:
            widgets["status_badge"].config(text="정상가동", fg="#34d399", bg="#064e3b")
            widgets["pbar"].config(style="TProgressbar")
            
        # Progress & Speed
        completed = prog.get("completed", 0) or 0
        total = prog.get("total", 0) or 1
        percent = prog.get("percent", 0) or int((completed / total) * 100 if total else 0)
        units_hr = prog.get("units_per_hour", 0.0) or 0.0
        
        widgets["pbar"]["value"] = percent
        widgets["prog_lbl"].config(text=f"{completed}/{total} 청크 ({percent}%)")
        
        speed_text = f"⚡ {units_hr:.1f} c/h" if units_hr > 0 else "⚡ 대기 중"
        widgets["speed_lbl"].config(text=speed_text)
        
        # Stage label
        stage_label = wf.get("stage_label", "")
        stage = wf.get("stage", "")
        detail = wf.get("detail", "")
        display_stage = f"{stage_label} ({stage})" if stage_label else f"{stage} - {detail}"
        widgets["stage_lbl"].config(text=display_stage[:55])


def main():
    root = tk.Tk()
    app = StatusHudApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
