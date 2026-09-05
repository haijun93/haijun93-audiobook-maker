# Master Library Taxonomy & Classification Standard

> **문서 버전**: 1.0 (2026-08-17)  
> **적용 서재 루트**:  
> 1. 로컬: `/Users/hyeokjunkong/Desktop/소설2/`  
> 2. Google Drive: `/Users/hyeokjunkong/Library/CloudStorage/GoogleDrive-haijun93@gmail.com/.shortcut-targets-by-id/16Rb7wC9JJw_rgMVEnDerFiY4JbFsC0aF/#Books/`

---

## 1. 4대 표준 에디션 디렉터리 체계

모든 번역 완료 도서는 다음 4개 루트 디렉터리 하위에 동일한 상대 경로(1:1 Mirroring)로 입고됩니다:

| 에디션 태그 | 디렉터리명 | 설명 | 생성 파이프라인 |
|---|---|---|---|
| `[k-e]` | `소설2/[k-e]/` | 한영 대조본 (Bilingual) | LLM 번역 직후 1차 빌드 |
| `[k]` | `소설2/[k]/` | 한글 전용본 (Korean-only) | `make_korean_only_epubs.py` 파생 |
| `[study]` | `소설2/[study]/` | 한글 + TOEIC 700+ 어휘/표현 학습노트 | `translate_epub_with_chatgpt_web_to_study_epub.py` |
| `[e-s]` | `소설2/[e-s]/` | 영문 원서 + TOEIC 700+ 학습노트 | `make_english_study_epubs.py` 파생 |

---

## 2. 대분류 장르 및 작가별 표준 경로 규칙

### (1) Best 100 및 주요 장르 대분류 (`[k]`, `[k-e]`, `[study]`, `[e-s]` 공통)

1. **`Fiction_Literary_Historical/` (문학/역사소설 대작)**
   - `#Hanya Yanagihara/` (A Little Life)
   - `#Gabrielle Zevin/` (Tomorrow and Tomorrow and Tomorrow)
   - `#Barbara Kingsolver/` (Demon Copperhead)
   - `#Fredrik Backman/` (Beartown)
   - `#Khaled Hosseini/` (The Kite Runner, A Thousand Splendid Suns)
   - `#Ursula Rani Sarma/` (A Thousand Splendid Suns)
   - `#Arthur Golden/` (Memoirs of a Geisha)
   - `#Ken Follett/` (World Without End, The Pillars of the Earth)
   - `#Markus Zusak/` (The Book Thief)
   - `#Paulo Coelho/` (The Alchemist, Eleven Minutes, The Pilgrimage)
   - `#Patrick Süskind/` (Perfume: The Story of a Murderer)

2. **`Mystery_Thriller_Crime/` (미스터리/스릴러/범죄)**
   - `#Alex Michaelides/` (The Silent Patient, The Maidens, The Fury)
   - `#Haper Lee/` (To Kill a Mockingbird)
   - `#Agatha Christie/` (And Then There Were None)
   - `#Keigo Higashino/` (The Devotion of Suspect X)
   - `#Lisa Jewell/` (None of This is True)
   - `#Stieg Larsson/` (The Girl with the Dragon Tattoo)

3. **`Fantasy_Science_Fiction/` (판타지/SF)**
   - `#Brandon Sanderson/` (Mistborn 시리즈: The Final Empire, The Well of Ascension, The Hero of Ages)
   - `#Suzanne Collins/` (Hunger Games: Mockingjay)
   - `#Isaac Asimov/` (Foundation)
   - `#Guy Gavriel Kay/` (The Summer Tree)

4. **`Romance_Contemporary/` (현대 로맨스)**
   - `#Abby Jimenez/` (The Fall Risk)
   - `#Casey McQuiston/` (Red, White & Royal Blue)
   - `#Ali Hazelwood/`, `#Rebecca Yarros/`

5. **기타 장르 대분류**
   - `Historical_Fiction/#Mark Sullivan/` (Beneath a Scarlet Sky)
   - `Young_Adult_Children/#R J Palacio/` (Wonder 시리즈)
   - `Dark_Romance/#Author/`
   - `Nonfiction_History_Politics/#Author/`, `Business_Economics/#Author/`, `Biography_Memoir/#Author/`

---

### (2) 전작 컬렉션 특화 작가 폴더 (에디션 최상위 유지)

방대한 전작 카탈로그나 시리즈를 보유한 특화 작가는 각 에디션(`[k]`, `[k-e]`, `[study]`, `[e-s]`) 최상위에 정식 작가 폴더로 유지됩니다:

- 📂 `/#Freida McFadden/` (프리다 맥파든 전작 컬렉션)
- 📂 `/#Pam Godwin/` (팸 고드윈 전작 컬렉션)
- 📂 `/#Leigh Rivers/` (리 리버스 다크로맨스 컬렉션)
- 📂 `/#Top 10 dark romance/` (VK 10대 다크로맨스 컬렉션)

---

## 3. 유지관리 및 검수 원칙

1. **상호 1:1 디렉터리 미러링**:
   - `[k]`, `[k-e]`, `[study]`, `[e-s]` 중 어느 하나의 위치가 변경되면 나머지 3개 에디션도 100% 동일한 상대 경로로 함께 이동/동기화한다.
2. **임시 폴더 생성 금지**:
   - `pam_general_translation`이나 `[study]/[e-s]` 같은 임시 디렉터리를 서재 루트에 생성하지 않는다.
3. **루트 파일 금지**:
   - 각 에디션 최상위 루트에 분류되지 않은 `.epub` 파일이 방치되지 않도록 항상 장르/작가 폴더로 입고한다.
