#!/usr/bin/env python3
"""
Ollama Local M1 Max LLM Engine (Gemma 4 Optimized)
Leverages Apple Silicon M1 Max 32GB Unified Memory & Metal GPU Acceleration.
Zero API cost, zero network latency, zero Cloudflare WAF issues.
"""

import json
import urllib.request
import urllib.error
import time

OLLAMA_API_CHAT_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "gemma4:latest"

def is_ollama_available() -> bool:
    try:
        req = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
        return req.status == 200
    except Exception:
        return False

def query_ollama_gemma(prompt: str, system_prompt: str = "", model: str = DEFAULT_MODEL, timeout_sec: int = 180) -> str:
    """Queries local Ollama Gemma model with M1 Max Metal acceleration via /api/chat"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_API_CHAT_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            msg = body.get("message", {})
            return msg.get("content", "").strip()
    except Exception as e:
        raise RuntimeError(f"Ollama local inference error: {e}")

def extract_study_notes_local(chunk_text: str, model: str = DEFAULT_MODEL) -> dict:
    """Extracts TOEIC 700+ vocabulary & grammar explanations locally in seconds"""
    sys_prompt = (
        "You are an expert English-Korean educator. Analyze the provided English text and extract "
        "TOEIC 700+ target vocabulary, idioms, complex grammatical structures, and cultural context. "
        "Output ONLY valid JSON with keys: 'vocabulary' (list of {word, meaning, example}), "
        "'grammar_points' (list of {pattern, explanation, sentence}), 'summary_ko'."
    )
    prompt = f"English Text Chunk:\n\n{chunk_text}\n\nOutput JSON:"
    res_text = query_ollama_gemma(prompt, system_prompt=sys_prompt, model=model)

    # Clean JSON
    clean_json = res_text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except Exception:
        return {"raw_notes": res_text}

if __name__ == "__main__":
    print("Testing Ollama M1 Max Local Engine with /api/chat...")
    if is_ollama_available():
        test_prompt = "Translate this into natural, immersive Korean: 'The old clock on the mantelpiece ticked steadily, measuring out the quiet rhythm of the afternoon.'"
        t0 = time.time()
        out = query_ollama_gemma(test_prompt)
        elapsed = time.time() - t0
        print(f"✅ Success in {elapsed:.2f}s!")
        print("Output:\n", out)
    else:
        print("❌ Ollama server is not running on localhost:11434")
