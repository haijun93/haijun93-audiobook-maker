#!/usr/bin/env python3
"""scripts/clean_and_purify_legacy_study_notes.py

Cleans and purifies study notes in legacy books:
1. Removes cross-novel contaminated situational sentences (e.g. "골리스 마켓에서...", quotes, narrative residue).
2. Strips overly specific situational bracket annotations.
3. Replaces / sanitizes word definitions to pure, standard English-Korean dictionary meanings.
4. Deduplicates terms within paragraph notes.
5. Applies cleanly to [study] and [e-s] editions.
"""

import zipfile
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor

# Common standard dictionary fallback overrides for overly specific terms
STANDARD_DICT_OVERRIDES = {
    "problem": "문제, 곤란한 일",
    "without": "~ 없이, ~하지 않고",
    "tonight": "오늘 밤에, 오늘 밤",
    "andrew": "앤드루 (인명)",
    "stuck": "갇힌, 꼼짝 못 하는",
    "regretful": "유감스러운, 후회하는",
    "quarter": "4분의 1, 15분, 25센트",
    "seven": "7, 일곱",
    "back": "뒤로, 다시, 답하여",
    "drive safely": "안전 운전하다",
    "with disappointment": "실망하여, 실망스럽게",
    "flick through": "재빨리 넘겨보다, 훑어보다",
    "reeling with": "~로 휘청거리는, 비틀거리는",
    "feels like": "~처럼 느껴지다",
    "the whole": "전체의, 온통 ~인",
    "not here": "여기에 없는",
    "shopping trip": "쇼핑하러 다녀오기",
    "even though": "비록 ~일지라도",
    "the house": "집, 가문",
    "secret": "비밀, 기밀",
    "locked door": "잠긴 문",
    "remember": "기억하다, 기억해내다",
    "the housemaid": "하우스메이드, 가정부",
    "not disturb": "방해하지 않다",
    "poverty": "빈곤, 가난",
    "easier": "더 쉬운",
    "unpaid bills": "미납 청구서, 밀린 공과금",
    "child": "아이, 어린이",
    "yelling": "고함, 소리침",
    "maintenance": "유지, 관리, 보수",
    "said": "말했다",
    "dad": "아빠, 아버지",
    "tap": "가볍게 두드리다, 수도꼭지",
    "pickle": "피클, 절임",
}

def clean_single_entry(word: str, definition: str) -> str:
    word_clean = word.strip()
    word_lower = word_clean.lower()
    
    if word_lower in STANDARD_DICT_OVERRIDES:
        return f"{word_clean} - {STANDARD_DICT_OVERRIDES[word_lower]}"
        
    def_clean = definition.strip()
    
    # 1. Remove long narrative quotes or complete sentences (length > 15 containing Korean period or narrative endings)
    # e.g., "사 오라며 장보기 목록을 보내놓고는, 콩 통조림 값이 두 배로 올랐다고 기겁을 하곤 했다."
    def_clean = re.sub(r'["“][^"”]+["”]', '', def_clean)
    def_clean = re.sub(r'[가-힣\s,]+(?:했다|하곤 했다|뜻이다|것이다|있었다|말했다|보았다|생각했다|어림짐작만)\b.*', '', def_clean)
    
    # 2. Remove specific cross-novel situational parenthesis
    # e.g., "(Chapter Seven은 제7장)", "(출판 업계에서)", "(이혼 후의)", "(실험·시험에서의)"
    def_clean = re.sub(r'\([가-힣a-zA-Z0-9\s·\-_,]+은\s+[제Chapter0-9]+[가-힣a-zA-Z0-9\s]*\)', '', def_clean)
    def_clean = re.sub(r'\([가-힣\s]+(?:에서|후의|업계에서|상황|배가|대화|호칭)\)', '', def_clean)
    
    # Clean up trailing punctuation, whitespace
    def_clean = re.sub(r'[\s,;]+$', '', def_clean).strip()
    
    # If definition became empty or invalid, fallback to pure word
    if not def_clean or len(def_clean) < 1:
        def_clean = "사전적 의미"
        
    return f"{word_clean} - {def_clean}"

def purify_study_note_text(raw_text: str) -> str:
    # Strip leading ※ or ※학습:
    content = re.sub(r'^※\s*(?:학습\s*:\s*)?', '', raw_text.strip())
    items = content.split(";")
    
    cleaned_items = []
    seen_words = set()
    
    for item in items:
        item = item.strip()
        if not item or "-" not in item:
            continue
        parts = item.split("-", 1)
        w = parts[0].strip()
        d = parts[1].strip() if len(parts) > 1 else ""
        
        w_norm = w.lower()
        if w_norm in seen_words:
            continue
        seen_words.add(w_norm)
        
        entry = clean_single_entry(w, d)
        if entry:
            cleaned_items.append(entry)
            
    if not cleaned_items:
        return ""
        
    return "※ " + "; ".join(cleaned_items)

def process_epub(epub_path: Path) -> bool:
    try:
        temp_path = epub_path.with_suffix(".tmp.epub")
        modified = False
        
        with zipfile.ZipFile(epub_path, 'r') as zin, zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(('.xhtml', '.html')):
                    text = data.decode('utf-8', errors='ignore')
                    if 'class="study-note"' in text or "class='study-note'" in text:
                        soup = BeautifulSoup(text, 'html.parser')
                        notes = soup.find_all(class_='study-note')
                        if notes:
                            for n in notes:
                                original_txt = n.get_text()
                                purified = purify_study_note_text(original_txt)
                                if purified:
                                    n.string = purified
                                else:
                                    n.decompose()
                            data = str(soup).encode('utf-8')
                            modified = True
                zout.writestr(item, data)
                
        if modified:
            shutil.move(temp_path, epub_path)
            return True
        else:
            if temp_path.exists():
                temp_path.unlink()
            return False
    except Exception as exc:
        temp_path = epub_path.with_suffix(".tmp.epub")
        if temp_path.exists():
            temp_path.unlink()
        return False

def main():
    lib_root = Path("/Users/hyeokjunkong/Desktop/소설2")
    study_epubs = list((lib_root / "[study]").rglob("*.epub")) + list((lib_root / "[e-s]").rglob("*.epub"))
    study_epubs = [p for p in study_epubs if not p.name.startswith("._")]
    
    print("==================================================================")
    print(f"🧹 PURIFYING STUDY NOTES TO PURE DICTIONARY DEFINITIONS ({len(study_epubs)} books)")
    print("==================================================================")
    
    success_cnt = 0
    with ProcessPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(process_epub, study_epubs))
        success_cnt = sum(1 for r in results if r)
        
    print(f"🎉 Successfully purified study notes in {success_cnt} / {len(study_epubs)} books!")
    print("==================================================================")

if __name__ == "__main__":
    main()
