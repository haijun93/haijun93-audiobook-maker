# Korean Audiobook Maker

Create Korean audiobooks from TXT, EPUB, DOCX, and PDF files, or translate
English EPUB, PDF, and MOBI books into Korean and bilingual study editions.
Use the local web interface for everyday work or the CLI for automation and
long-running jobs.

The project supports three voice providers:

- `gemini_api_tts`: Gemini Developer API TTS
- `gemini_web`: Gemini's signed-in web interface
- `chatgpt_web`: ChatGPT's signed-in web interface and read-aloud feature

> Use only documents you own or have permission to process. You are
> responsible for provider terms, API charges, and the rights to generated
> output.

## Web Interface

Python 3.11 or newer is required.

```bash
git clone https://github.com/haijun93/haijun93-audiobook-maker.git
cd haijun93-audiobook-maker
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
audiobook-maker-web
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860). The interface provides:

- audio generation from an uploaded file or pasted text, including Gemini Web
- English EPUB/PDF/MOBI translation into `[k]` Korean and `[k-e]` bilingual EPUBs
- folder scanning and queued batch translation or audio generation
- persistent jobs, live logs, result playback, and individual file downloads

Folder jobs use paths on the computer running the server. By default,
translations are written to `[k]` and `[k-e]` folders inside the selected
source folder, while audio is written to its `audiobooks` folder. Enter a
different output path to keep results elsewhere.

Windows activation:

```powershell
.venv\Scripts\activate
```

Run without installing command aliases:

```bash
python web_app.py
```

The server listens only on localhost by default. It has no built-in account
system, so do not expose it to a network without an authenticated reverse
proxy. See [SECURITY.md](SECURITY.md).

## Provider Setup

### Gemini API TTS

Create an API key for a project that can access Gemini TTS, then set one of:

```bash
export GEMINI_API_KEY="your_api_key"
# or: export GOOGLE_API_KEY="your_api_key"
```

The default model is `gemini-2.5-flash-preview-tts` and the default voice is
`Sulafat`.

### Gemini Web and ChatGPT Web

Install Google Chrome and sign in to the provider in your regular Chrome
profile. Chrome is discovered automatically on macOS, Windows, and Linux. A
custom executable can be selected with:

```bash
export AUDIOBOOK_CHROME_PATH="/path/to/chrome"
```

Playwright may need a one-time browser installation:

```bash
python -m playwright install chromium
```

Web automation depends on the provider's current UI, account limits, login
state, and network. The job log reports retries and actionable failures.

### Book Translation

Gemini Web is the default translation provider. The translation workflow first
builds a character relationship and speech-level guide, translates the book,
then performs final tone and dialogue consistency checks. It produces a
sentence-paired bilingual EPUB and can derive a Korean-only edition from it.

PDF sources are converted to a reflowable English EPUB before translation, so
complex fixed-layout pages may not retain their original visual arrangement.
MOBI input requires [Calibre](https://calibre-ebook.com/) and its
`ebook-convert` command. Calibre is discovered automatically in common install
locations, or it can be configured explicitly:

```bash
export EBOOK_CONVERT_PATH="/path/to/ebook-convert"
```

## CLI

Gemini API example:

```bash
audiobook-maker \
  --provider gemini_api_tts \
  --input-file "./book.epub" \
  --output-file "./audiobooks/book.m4a" \
  --voice Sulafat
```

Gemini Web example:

```bash
audiobook-maker \
  --provider gemini_web \
  --input-file "./book.txt" \
  --output-file "./audiobooks/book.m4a" \
  --voice account_default
```

ChatGPT Web example:

```bash
audiobook-maker \
  --provider chatgpt_web \
  --input-file "./book.txt" \
  --output-file "./audiobooks/book.m4a" \
  --voice cove
```

Run `audiobook-maker --help` for all provider, chunking, retry, study-mode,
heartbeat, and output options.

## Audiobook Modes

- `plain`: read the extracted source text
- `material_only`: omit surrounding answer or explanation material where the
  source format supports it
- `study`: organize sections as summaries, memory points, reminders, and
  transitions

EPUB input follows spine order. DOCX input uses paragraph and heading styles.
PDF input reads text blocks and preserves major section boundaries where they
can be detected. Adjacent short sections are grouped to avoid choppy audio.

## Long-Running Jobs

Shell wrappers in `scripts/` add a watchdog, heartbeat files, retry settings,
and resumable work directories. For example:

```bash
MAX_CHARS=2500 \
./scripts/run_gemini_api_tts_job.sh \
  "./book.epub" \
  "./audiobooks/book.m4a"
```

Common watchdog settings:

- `WATCHDOG_STALL_SEC`: maximum time without heartbeat or output activity
- `WATCHDOG_POLL_SEC`: watchdog polling interval
- `WATCHDOG_KILL_GRACE_SEC`: graceful shutdown period before forced shutdown

Intermediate text, responses, metadata, audio segments, and a manifest remain
in the job work directory so interrupted work can continue.

## Configuration

Copy `.env.example` to `.env.local` or export the same variables in the shell.
The web interface recognizes:

- `AUDIOBOOK_WEB_HOST` (default `127.0.0.1`)
- `AUDIOBOOK_WEB_PORT` (default `7860`)
- `AUDIOBOOK_WEB_DATA_DIR` (default `.webui`)
- `AUDIOBOOK_MAX_UPLOAD_MB` (default `100`)
- `AUDIOBOOK_CHROME_PATH`
- `EBOOK_CONVERT_PATH`
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`

Uploaded documents and generated files are stored below
`AUDIOBOOK_WEB_DATA_DIR`. Folder-batch results are stored in the output path
selected in the interface. Job metadata is written atomically, and active jobs
return to the queue after a web server restart.

## Development

```bash
python -m pip install -e ".[dev]"
python scripts/quality_gate.py
```

The quality gate runs dependency checks, Ruff, Python compilation, zsh syntax
validation, the full test suite, and Git whitespace validation. GitHub Actions
runs the same checks on Python 3.11 and 3.13.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

Korean Audiobook Maker is released under the [MIT License](LICENSE). Selected
Lucide icons are included under the terms in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## 한국어 빠른 안내

이 프로젝트는 `txt`, `epub`, `docx`, `pdf`를 오디오북으로 변환하고,
영문 `epub`, `pdf`, `mobi`를 `[k]` 한글 EPUB과 `[k-e]` 한영 EPUB으로
번역합니다. 폴더 경로를 지정하면 번역이나 오디오 생성을 일괄 처리할
수 있습니다. 처음 사용하는 경우 위 설치 명령을 실행한 뒤
`audiobook-maker-web`을 시작하고 브라우저에서
`http://127.0.0.1:7860`을 여세요.

Gemini API 방식에는 `GEMINI_API_KEY`가 필요합니다. Gemini Web과 ChatGPT
Web 방식은 Chrome 로그인 세션을 사용합니다. 웹 화면의 작업 목록에서
진행률과 로그를 확인하고, 완료된 오디오를 재생하거나 각 EPUB 결과물을
내려받을 수 있습니다. MOBI 변환에는 Calibre가 필요합니다.
