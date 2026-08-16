#!/usr/bin/env python3
"""
Always-On-Top Floating Native Web Dashboard for Audiobook Maker
http://127.0.0.1:7870 웹 대시보드 화면 자체를 '항상 위(Always on Top)' 네이티브 플로팅 창으로 띄웁니다.
"""

import sys
import webview


def main():
    url = "http://127.0.0.1:7870/"
    title = "🎧 Audiobook Studio - 실시간 대시보드 (Always on Top)"
    
    # Create an Always-on-top window loading the full web app UI
    window = webview.create_window(
        title=title,
        url=url,
        width=1100,
        height=780,
        resizable=True,
        on_top=True,  # 항상 위에 고정
        shadow=True,
        background_color="#121316",
    )
    
    # Start webview using native macOS Cocoa WebKit engine
    webview.start(debug=False)


if __name__ == "__main__":
    main()
