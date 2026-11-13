"""Запуск: python lab4/app/server.py. Інструкція: README.md у цій теці."""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import time
import urllib.parse
import urllib.request

from core import AppError, Settings, generate

WEB = Path(__file__).parent / "web"
SETTINGS = Settings(base_url=os.getenv("LOCAL_MODEL_BASE_URL", "http://127.0.0.1:8080/v1"),
                    model=os.getenv("LOCAL_MODEL_NAME", "game-bug-qwen3"))


class Handler(BaseHTTPRequestHandler):
    def send_data(self, data, status=200, content_type="application/json; charset=utf-8"):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8") if not isinstance(data, bytes) else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/config":
            self.send_data({"model": SETTINGS.model, "temperature": SETTINGS.temperature,
                            "max_tokens": SETTINGS.max_tokens, "context_length": SETTINGS.context_length})
        elif path == "/api/health":
            try:
                with urllib.request.urlopen(SETTINGS.base_url.rstrip("/") + "/models", timeout=3) as response:
                    models = json.load(response)
                ready = any(item.get("id") == SETTINGS.model for item in models.get("data", []))
                self.send_data({"ready": ready, "message": "Модель готова" if ready else "Потрібно завантажити модель"})
            except Exception:
                self.send_data({"ready": False, "message": "Сервер моделі недоступний"})
        elif path in {"/", "/index.html", "/style.css", "/app.js"}:
            filename = "index.html" if path == "/" else path[1:]
            mime = {"html": "text/html", "css": "text/css", "js": "text/javascript"}[filename.rsplit(".", 1)[1]]
            self.send_data((WEB / filename).read_bytes(), content_type=mime + "; charset=utf-8")
        else:
            self.send_data({"error": "Сторінку не знайдено."}, 404)

    def do_POST(self):
        if self.path != "/api/generate":
            return self.send_data({"error": "Адресу не знайдено."}, 404)
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
            return self.send_data({"error": "Запит з іншого сайту заборонено."}, 403)
        if self.headers.get_content_type() != "application/json":
            return self.send_data({"error": "Потрібний запит у форматі JSON."}, 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 20000:
                raise AppError("Некоректний розмір запиту.", 400)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise AppError("Очікується JSON-об’єкт з описом бага.", 400)
            start = time.perf_counter()
            result = generate(body.get("description"), SETTINGS)
            result["elapsed_s"] = round(time.perf_counter() - start, 2)
            self.send_data(result)
        except AppError as exc:
            self.send_data({"error": str(exc)}, exc.status)
        except (ValueError, UnicodeDecodeError):
            self.send_data({"error": "Не вдалося прочитати JSON-запит."}, 400)
        except Exception:
            self.send_data({"error": "Не вдалося завершити запит. Перевірте сервер моделі."}, 500)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Генератор баг-репортів для ігор")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Відкрийте http://127.0.0.1:{args.port}. Модель: {SETTINGS.model}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
