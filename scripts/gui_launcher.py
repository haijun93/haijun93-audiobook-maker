#!/usr/bin/env python3
"""
Audiobook Studio - macOS GUI Controller & Launcher
작업 개시, 작업 중단, 새로고침, 종료 기능을 제공하는 독립 실행 컨트롤러 GUI
"""

import json
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = ROOT / ".venv311" / "bin" / "python"
SCHEDULER_CONFIG = ROOT / ".work" / "continuous_scheduler" / "config.json"
SCHEDULER_STATE_DIR = ROOT / ".work" / "continuous_scheduler"
WEB_URL = "http://127.0.0.1:7870/"
API_BATCH_REPORT = "http://127.0.0.1:7870/api/batch-report"


class AudiobookStudioController:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Audiobook Studio - 작업 컨트롤러")
        self.root.geometry("540x620+100+100")
        self.root.minsize(480, 520)
        self.root.configure(bg="#0f172a")

        self.running = True
        self._setup_styles()
        self._build_ui()

        # Initial check & polling thread
        self.poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.poll_thread.start()

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TProgressbar",
                             thickness=10,
                             troughcolor="#1e293b",
                             background="#0284c7",
                             bordercolor="#1e293b",
                             lightcolor="#38bdf8",
                             darkcolor="#0284c7")

    def _build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg="#1e293b", padx=16, pady=12)
        header.pack(fill="x", side="top")

        title_box = tk.Frame(header, bg="#1e293b")
        title_box.pack(side="left")

        title_lbl = tk.Label(title_box, text="🎧 Audiobook Studio 컨트롤러",
                             font=("SF Pro Display", 14, "bold"),
                             fg="#f8fafc", bg="#1e293b")
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(title_box, text="실시간 번역 및 오디오북 통합 관리 시스템",
                           font=("SF Pro Text", 10),
                           fg="#94a3b8", bg="#1e293b")
        sub_lbl.pack(anchor="w")

        web_btn = tk.Button(header, text="🌐 웹 대시보드 열기",
                            font=("SF Pro Text", 10, "bold"),
                            fg="#38bdf8", bg="#0f172a",
                            activebackground="#334155", activeforeground="#ffffff",
                            relief="flat", padx=10, pady=5, cursor="pointinghand",
                            command=lambda: webbrowser.open(WEB_URL))
        web_btn.pack(side="right")

        # 2. Main Content Frame
        content = tk.Frame(self.root, bg="#0f172a", padx=16, pady=12)
        content.pack(fill="both", expand=True)

        # System Status Box
        sys_frame = tk.LabelFrame(content, text=" 🖥️ 시스템 및 서비스 상태 ",
                                  font=("SF Pro Text", 10, "bold"),
                                  fg="#cbd5e1", bg="#1e293b", padx=12, pady=10, bd=1)
        sys_frame.pack(fill="x", pady=(0, 10))

        self.web_status_lbl = tk.Label(sys_frame, text="• 웹서버 (포트 7870): 확인 중...",
                                       font=("SF Pro Text", 10), fg="#94a3b8", bg="#1e293b", anchor="w")
        self.web_status_lbl.pack(fill="x", pady=2)

        self.sched_status_lbl = tk.Label(sys_frame, text="• 배치 스케줄러: 확인 중...",
                                         font=("SF Pro Text", 10), fg="#94a3b8", bg="#1e293b", anchor="w")
        self.sched_status_lbl.pack(fill="x", pady=2)

        # Account Status Box
        acc_frame = tk.LabelFrame(content, text=" 🔑 계정별 실시간 로그인 상태 ",
                                  font=("SF Pro Text", 10, "bold"),
                                  fg="#cbd5e1", bg="#1e293b", padx=12, pady=10, bd=1)
        acc_frame.pack(fill="x", pady=(0, 10))

        self.acc_labels = {}
        acc_names = [
            ("main", "계정 1 (haijun93)"),
            ("account2", "계정 2 (haijun2be)"),
            ("account3", "계정 3 (ngaytot9)"),
            ("chatgpt", "ChatGPT (haijun93)"),
        ]

        grid_frame = tk.Frame(acc_frame, bg="#1e293b")
        grid_frame.pack(fill="x")

        for idx, (aid, label) in enumerate(acc_names):
            row = idx // 2
            col = idx % 2
            lbl = tk.Label(grid_frame, text=f"• {label}: ⏳",
                           font=("SF Pro Text", 9, "bold"),
                           fg="#94a3b8", bg="#1e293b", anchor="w")
            lbl.grid(row=row, column=col, sticky="w", padx=6, pady=4)
            self.acc_labels[aid] = lbl

        # Live Tasks Progress Box
        tasks_frame = tk.LabelFrame(content, text=" ⚡ 실시간 번역 진행 현황 ",
                                    font=("SF Pro Text", 10, "bold"),
                                    fg="#cbd5e1", bg="#1e293b", padx=12, pady=10, bd=1)
        tasks_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.tasks_container = tk.Frame(tasks_frame, bg="#1e293b")
        self.tasks_container.pack(fill="both", expand=True)

        self.empty_task_lbl = tk.Label(self.tasks_container, text="작업 상태를 불러오는 중...",
                                       font=("SF Pro Text", 10), fg="#64748b", bg="#1e293b")
        self.empty_task_lbl.pack(pady=20)

        # 3. Action Buttons Toolbar (하단 4대 버튼)
        btn_toolbar = tk.Frame(self.root, bg="#1e293b", padx=16, pady=14)
        btn_toolbar.pack(fill="x", side="bottom")

        # Start Button (작업 개시)
        self.start_btn = tk.Button(btn_toolbar, text="▶️ 작업 개시",
                                   font=("SF Pro Text", 11, "bold"),
                                   fg="#ffffff", bg="#15803d",
                                   activebackground="#166534", activeforeground="#ffffff",
                                   relief="flat", padx=14, pady=8, cursor="pointinghand",
                                   command=self.start_all_tasks)
        self.start_btn.pack(side="left", padx=(0, 6), expand=True, fill="x")

        # Stop Button (작업 중단)
        self.stop_btn = tk.Button(btn_toolbar, text="⏸️ 작업 중단",
                                  font=("SF Pro Text", 11, "bold"),
                                  fg="#ffffff", bg="#b91c1c",
                                  activebackground="#991b1b", activeforeground="#ffffff",
                                  relief="flat", padx=14, pady=8, cursor="pointinghand",
                                  command=self.stop_all_tasks)
        self.stop_btn.pack(side="left", padx=6, expand=True, fill="x")

        # Refresh Button (새로고침)
        self.refresh_btn = tk.Button(btn_toolbar, text="🔄 새로고침",
                                     font=("SF Pro Text", 11, "bold"),
                                     fg="#ffffff", bg="#0284c7",
                                     activebackground="#0369a1", activeforeground="#ffffff",
                                     relief="flat", padx=14, pady=8, cursor="pointinghand",
                                     command=self.refresh_audit_now)
        self.refresh_btn.pack(side="left", padx=6, expand=True, fill="x")

        # Quit Button (종료)
        self.quit_btn = tk.Button(btn_toolbar, text="❌ 종료",
                                  font=("SF Pro Text", 11, "bold"),
                                  fg="#ffffff", bg="#475569",
                                  activebackground="#334155", activeforeground="#ffffff",
                                  relief="flat", padx=14, pady=8, cursor="pointinghand",
                                  command=self.quit_app)
        self.quit_btn.pack(side="left", padx=(6, 0), expand=True, fill="x")

    def _is_web_server_running(self) -> bool:
        try:
            req = urllib.request.Request(WEB_URL, headers={"User-Agent": "Controller/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _is_scheduler_running(self) -> bool:
        try:
            res = subprocess.run(["pgrep", "-f", "run_continuous_translation_scheduler"],
                                 capture_output=True, text=True)
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception:
            return False

    def _polling_loop(self):
        while self.running:
            try:
                web_ok = self._is_web_server_running()
                sched_ok = self._is_scheduler_running()

                # Fetch batch report if web is ok
                report_data = None
                if web_ok:
                    try:
                        req = urllib.request.Request(API_BATCH_REPORT, headers={"User-Agent": "Controller/1.0"})
                        with urllib.request.urlopen(req, timeout=2.0) as resp:
                            report_data = json.loads(resp.read().decode("utf-8"))
                    except Exception:
                        pass

                self.root.after(0, self._update_ui_state, web_ok, sched_ok, report_data)
            except Exception:
                pass
            time.sleep(2.0)

    def _update_ui_state(self, web_ok: bool, sched_ok: bool, report_data: dict | None):
        # 1. Web status
        if web_ok:
            self.web_status_lbl.config(text="• 웹서버 (포트 7870): 🟢 정상 작동 중 (http://127.0.0.1:7870)", fg="#4ade80")
        else:
            self.web_status_lbl.config(text="• 웹서버 (포트 7870): ⚪ 정지됨", fg="#94a3b8")

        # 2. Scheduler status
        if sched_ok:
            self.sched_status_lbl.config(text="• 배치 스케줄러: 🟢 실시간 번역 진행 중", fg="#4ade80")
        else:
            self.sched_status_lbl.config(text="• 배치 스케줄러: ⚪ 정지됨 (작업 개시 버튼을 누르세요)", fg="#f59e0b")

        # 3. Account login states
        if report_data and "accounts" in report_data:
            accounts = report_data["accounts"]
            for aid, lbl in self.acc_labels.items():
                acc = accounts.get(aid, {})
                is_ok = acc.get("logged_in", False)
                name = acc.get("label", aid)
                if is_ok:
                    lbl.config(text=f"• {name}: 🟢 정상", fg="#4ade80")
                else:
                    lbl.config(text=f"• {name}: 🟡 로그인 필요", fg="#fbbf24")

        # 4. Live tasks
        if report_data and "active_tasks" in report_data:
            active_tasks = report_data["active_tasks"]
            for child in self.tasks_container.winfo_children():
                child.destroy()

            if not active_tasks:
                empty_lbl = tk.Label(self.tasks_container, text="현재 실행 중인 번역 작업이 없습니다.",
                                     font=("SF Pro Text", 10), fg="#64748b", bg="#1e293b")
                empty_lbl.pack(pady=20)
            else:
                for t in active_tasks[:3]:
                    card = tk.Frame(self.tasks_container, bg="#0f172a", padx=10, pady=8, bd=0)
                    card.pack(fill="x", pady=4)

                    r1 = tk.Frame(card, bg="#0f172a")
                    r1.pack(fill="x")

                    title_lbl = tk.Label(r1, text=f"📖 {t.get('title', '')}", font=("SF Pro Text", 10, "bold"),
                                         fg="#f8fafc", bg="#0f172a", anchor="w")
                    title_lbl.pack(side="left")

                    pct = t.get("progress_percent", 0)
                    pct_lbl = tk.Label(r1, text=f"{pct}%", font=("SF Pro Text", 10, "bold"),
                                       fg="#38bdf8", bg="#0f172a")
                    pct_lbl.pack(side="right")

                    r2 = tk.Frame(card, bg="#0f172a", pady=4)
                    r2.pack(fill="x")
                    pbar = ttk.Progressbar(r2, style="TProgressbar", orient="horizontal", mode="determinate", value=pct)
                    pbar.pack(fill="x")

                    r3 = tk.Frame(card, bg="#0f172a")
                    r3.pack(fill="x")
                    label_lbl = tk.Label(r3, text=f"{t.get('label', '')} ({t.get('account_id', '')})",
                                         font=("SF Pro Text", 9), fg="#94a3b8", bg="#0f172a")
                    label_lbl.pack(side="left")

    def start_all_tasks(self):
        """작업 개시 버튼: 웹서버 & 스케줄러 기동 및 웹 대시보드 열기"""
        self.start_btn.config(state="disabled")
        try:
            # 1. Start web app if not running
            if not self._is_web_server_running():
                subprocess.Popen(
                    [str(PYTHON_BIN), str(ROOT / "web_app.py"), "--port", "7870"],
                    cwd=str(ROOT),
                    stdout=open(ROOT / ".work" / "web_app.stdout.log", "a"),
                    stderr=open(ROOT / ".work" / "web_app.stderr.log", "a"),
                )

            # 2. Start scheduler if not running
            if not self._is_scheduler_running():
                subprocess.Popen(
                    [
                        str(PYTHON_BIN), "-m", "scripts.run_continuous_translation_scheduler",
                        "run", "--config", str(SCHEDULER_CONFIG), "--state-dir", str(SCHEDULER_STATE_DIR),
                    ],
                    cwd=str(ROOT),
                    stdout=open(SCHEDULER_STATE_DIR / "scheduler.stdout.log", "a"),
                    stderr=open(SCHEDULER_STATE_DIR / "scheduler.stderr.log", "a"),
                )

            # 3. Open browser
            time.sleep(1.0)
            webbrowser.open(WEB_URL)
            messagebox.showinfo("작업 개시 완료", "웹서버 및 배치 번역 스케줄러가 정상 시작되었습니다.\n브라우저 대시보드가 열립니다.")
        except Exception as exc:
            messagebox.showerror("작업 개시 실패", f"오류가 발생했습니다: {exc}")
        finally:
            self.start_btn.config(state="normal")

    def stop_all_tasks(self):
        """작업 중단 버튼: 실행 중인 번역 작업 및 스케줄러 안전 중단"""
        if not messagebox.askyesno("작업 중단 확인", "현재 진행 중인 번역 스케줄러와 번역 작업을 안전하게 중단하시겠습니까?"):
            return

        self.stop_btn.config(state="disabled")
        try:
            # Kill scheduler
            subprocess.run(["pkill", "-15", "-f", "run_continuous_translation_scheduler"], check=False)
            # Kill translation workers
            subprocess.run(["pkill", "-15", "-f", "translate_epub"], check=False)

            messagebox.showinfo("작업 중단 완료", "번역 스케줄러 및 번역 프로세스가 안전하게 중단되었습니다.")
        except Exception as exc:
            messagebox.showerror("작업 중단 실패", f"오류: {exc}")
        finally:
            self.stop_btn.config(state="normal")

    def refresh_audit_now(self):
        """새로고침 버튼: 즉시 계정 로그인 점검 및 배치 상태 갱신"""
        self.refresh_btn.config(state="disabled")
        try:
            subprocess.Popen([str(PYTHON_BIN), str(ROOT / "scripts" / "check_accounts_and_report.py")], cwd=str(ROOT))
            messagebox.showinfo("새로고침", "30분 정기 계정 및 배치 점검이 즉시 실행되었습니다.\n잠시 후 화면이 갱신됩니다.")
        except Exception as exc:
            messagebox.showerror("새로고침 실패", f"오류: {exc}")
        finally:
            self.root.after(2000, lambda: self.refresh_btn.config(state="normal"))

    def quit_app(self):
        """종료 버튼: 컨트롤러 종료"""
        self.running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = AudiobookStudioController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
