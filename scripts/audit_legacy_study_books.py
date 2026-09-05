#!/usr/bin/env python3
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

lib_root = Path("/Users/hyeokjunkong/Desktop/소설2")
study_dir = lib_root / "[study]"
study_epubs = list(study_dir.rglob("*.epub"))

legacy_count = 0
modern_count = 0
legacy_books = []
modern_books = []

for ep in study_epubs:
    if ep.name.startswith("._"):
        continue

    try:
        with zipfile.ZipFile(ep) as z:
            total_pairs = 0
            total_ko_len = 0
            xhtmls = [n for n in z.namelist() if n.endswith(".xhtml") or n.endswith(".html")]
            for x in xhtmls:
                if "nav" in x.lower() or "cover" in x.lower():
                    continue
                soup = BeautifulSoup(z.read(x), "html.parser")
                pairs = soup.find_all("p", class_="pair")
                total_pairs += len(pairs)
                for p in pairs:
                    ko_span = p.find("span", class_="ko")
                    if ko_span and ko_span.get_text(strip=True):
                        total_ko_len += len(ko_span.get_text(strip=True))

            # Check if true modern full context translation
            is_modern = total_pairs > 50 and total_ko_len > 10000
            if is_modern:
                modern_count += 1
                modern_books.append(ep)
            else:
                legacy_count += 1
                legacy_books.append((ep, total_pairs, total_ko_len))
    except Exception as exc:
        legacy_count += 1
        legacy_books.append((ep, 0, 0))

print("==================================================================")
print("📊 서재 내 [study] 에디션 도서 전수 번역 상태 정밀 감사")
print("==================================================================")
print(f"• 서재 내 [study] 총 도서 수             : {len(study_epubs)} 권")
print(f"• ✅ 신버전 AI 문맥 완역 완료된 도서      : {modern_count} 권")
print(f"• ⚠️ 구버전 상태로 신버전 재번역이 필요한 도서 : {legacy_count} 권")
print("==================================================================\n")

print("--- [신버전 완역 작업이 필요한 구버전 도서 샘플 25선] ---")
for idx, (ep, pairs, ko_len) in enumerate(legacy_books[:25], 1):
    rel_path = ep.relative_to(study_dir)
    print(f"{idx:2}. [한글 분량: {ko_len:,}자 | 문단쌍: {pairs}개] {rel_path}")
