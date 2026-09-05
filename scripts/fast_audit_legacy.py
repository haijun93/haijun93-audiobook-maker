#!/usr/bin/env python3
import zipfile
from pathlib import Path

lib_root = Path("/Users/hyeokjunkong/Desktop/소설2")
study_dir = lib_root / "[study]"
study_epubs = sorted([p for p in study_dir.rglob("*.epub") if not p.name.startswith("._")])

def main():
    print(f"Auditing {len(study_epubs)} books in [study] via ultra-fast byte scan...")

    modern = []
    legacy = []

    for ep in study_epubs:
        try:
            with zipfile.ZipFile(ep) as z:
                total_pairs = 0
                total_ko_bytes = 0
                for n in z.namelist():
                    if n.endswith((".xhtml", ".html")) and "nav" not in n.lower() and "cover" not in n.lower():
                        data = z.read(n)
                        # count pairs
                        pairs_cnt = data.count(b"class=\"pair\"") + data.count(b"class=\x27pair\x27")
                        total_pairs += pairs_cnt
                        if b"class=\"ko\"" in data or b"class=\x27ko\x27" in data:
                            total_ko_bytes += len(data)

                # A true modern AI translation has hundreds/thousands of pair paragraphs and substantial KO text
                if total_pairs > 50 and total_ko_bytes > 30000:
                    modern.append((ep, total_pairs))
                else:
                    legacy.append((ep, total_pairs))
        except Exception as exc:
            legacy.append((ep, 0))

    print("\n==================================================================")
    print("📊 서재 내 [study] 에디션 도서 전수 번역 상태 정밀 전수 조사 결과")
    print("==================================================================")
    print(f"• 서재 내 [study] 총 도서 수             : {len(study_epubs)} 권")
    print(f"• ✅ 신버전 AI 문맥 완역 완료 도서        : {len(modern)} 권")
    print(f"• ⚠️ 구버전(단순 단어주입/구형) 재번역 대상 : {len(legacy)} 권")
    print("==================================================================\n")

    print("--- [신버전 재번역 작업이 시급한 구버전 도서 샘플 30선] ---")
    for idx, (ep, pairs) in enumerate(legacy[:30], 1):
        rel = ep.relative_to(study_dir)
        print(f"{idx:2}. [문단쌍: {pairs:4}개] {rel}")

if __name__ == "__main__":
    main()
