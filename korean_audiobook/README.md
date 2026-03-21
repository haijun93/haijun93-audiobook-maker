# Korean Audiobook Prototype

한국어 장문 txt를 장별 MP3 오디오북으로 변환하는 1차 프로토타입입니다.

## 빠른 설치

```bash
python -m pip install -r requirements_korean_audiobook.txt
```

사용 가능한 엔진은 `edge`, `melo`, `xtts_v2`입니다.

`xtts_v2`를 쓰려면 Coqui TTS를 추가로 설치하세요.

```bash
python -m pip install TTS "transformers==4.46.3" torchcodec
```

`melo`를 쓰려면 공식 저장소를 설치하세요.

```bash
git clone https://github.com/myshell-ai/MeloTTS.git
cd MeloTTS
python -m pip install -e .
cd ..
```

## 기본 실행

가장 쉬운 기본 경로는 무료 `edge` 엔진입니다.

```bash
python -m korean_audiobook \
  --input-file "./smoke_ko.txt" \
  --output-dir "./korean_audiobook_runs/smoke_edge" \
  --title "스모크 테스트" \
  --author "Local" \
  --engine edge \
  --voice "ko-KR-SunHiNeural"
```

엔진 목록만 확인하려면:

```bash
python -m korean_audiobook --list-engines
```

XTTS-v2 예시:

```bash
python -m korean_audiobook \
  --input-file "./smoke_ko.txt" \
  --output-dir "./korean_audiobook_runs/smoke_xtts" \
  --title "스모크 테스트" \
  --author "Local" \
  --engine xtts_v2 \
  --speaker-wav "/path/authorized_reference.wav"
```

Melo 예시:

```bash
python -m korean_audiobook \
  --input-file "./smoke_ko.txt" \
  --output-dir "./korean_audiobook_runs/smoke_melo" \
  --title "스모크 테스트" \
  --author "Local" \
  --engine melo \
  --voice "KR"
```

## 출력 구조

- `chapters/*.mp3`: 장별 파일
- `<title>.mp3`: 전체 오디오북
- `<title>.m4b`: 선택 시 생성
- `audiobook_manifest.json`: 메타데이터와 장 정보
- `_cache/`: 문장 캐시
- `_work/`: 중간 wav와 상태 파일
