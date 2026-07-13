# Contributing

Thank you for improving Korean Audiobook Maker.

## Development setup

```bash
git clone https://github.com/haijun93/haijun93-audiobook-maker.git
cd haijun93-audiobook-maker
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

On Windows, activate the environment with `.venv\Scripts\activate`.

## Before a pull request

```bash
python scripts/quality_gate.py
```

Keep changes focused, add regression tests for behavior changes, and do not
commit API keys, browser profiles, copyrighted books, generated audio, or job
data. Web UI changes should work at both desktop and mobile widths.

## Reporting bugs

Include the operating system, Python version, selected provider, exact command
or UI action, and a redacted log excerpt. Never attach cookies or API keys.
