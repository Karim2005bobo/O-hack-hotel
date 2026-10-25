"""Запуск трип-агента с вводом ключа LLM в терминале.

    python run.py            # спросит ключ, адрес API и модель, затем запустит http://localhost:8080
    python run.py --port 9000

Ключ вводится скрыто и нигде не сохраняется: он живёт только в памяти запущенного
процесса. Нажмите Enter на вопросе о ключе — агент запустится без LLM (на встроенных правилах).
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

import httpx
import uvicorn


def ask(prompt: str, current: str | None = None) -> str:
    hint = f" [Enter — оставить {current}]" if current else ""
    value = input(f"{prompt}{hint}: ").strip()
    return value or (current or "")


def check(base: str, key: str, model: str) -> str | None:
    """Короткий пробный запрос. Возвращает текст ошибки или None, если всё работает."""
    try:
        r = httpx.post(f"{base.rstrip('/')}/chat/completions", timeout=40,
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                       json={"model": model, "messages": [{"role": "user", "content": "Ответь словом: ок"}], "max_tokens": 5})
    except httpx.HTTPError as e:
        return f"не удалось подключиться: {e}"
    if r.status_code == 200:
        return None
    hints = {401: "ключ не подходит", 402: "на балансе нет средств", 403: "доступ запрещён",
             404: "неверный адрес API или имя модели", 429: "превышен лимит запросов, попробуйте позже"}
    try:
        detail = r.json().get("error", {}).get("message", "")
    except ValueError:
        detail = r.text[:200]
    return f"HTTP {r.status_code}: {hints.get(r.status_code, 'ошибка сервиса')}. {detail}".strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Запуск трип-агента")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8080")))
    ap.add_argument("--no-check", action="store_true", help="не проверять подключение к LLM перед запуском")
    args = ap.parse_args()

    print("=== Трип-агент ===")
    print("Подключение LLM (любой OpenAI-совместимый API: OpenRouter, DeepSeek, Ollama и т. п.).")
    key = getpass.getpass("Ключ API (ввод скрыт; Enter — запуск без LLM): ").strip()
    if key:
        base = ask("Адрес API, например https://openrouter.ai/api/v1", os.getenv("LLM_BASE_URL"))
        model = ask("Модель, например meta-llama/llama-3.3-70b-instruct:free", os.getenv("LLM_MODEL"))
        if not base or not model:
            print("Не указан адрес API или модель — запускаю без LLM.")
            key = base = model = ""
        elif not args.no_check:
            print("Проверяю подключение…", end=" ", flush=True)
            err = check(base, key, model)
            if err:
                print(f"\n✕ {err}")
                if input("Запустить без LLM? [Y/n]: ").strip().lower() in ("n", "н", "no", "нет"):
                    sys.exit(1)
                key = base = model = ""
            else:
                print("✓ работает")
    else:
        base = model = ""
    # задаём явно (в т. ч. пустыми), чтобы значения из .env не подменили выбор в терминале
    os.environ["LLM_API_KEY"], os.environ["LLM_BASE_URL"], os.environ["LLM_MODEL"] = key, base, model
    print(f"Режим: {'LLM — ' + model if key else 'без LLM (встроенные правила)'}")
    print(f"Открывайте http://localhost:{args.port}  (остановить — Ctrl+C)")
    uvicorn.run("app.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
