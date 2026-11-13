"""Запускає модель і застосунок; Ctrl+C зупиняє обидва власні процеси."""
import argparse
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Локальний запуск ІгроЗвіту")
    parser.add_argument("--runtime-only", action="store_true", help="Запустити лише модель для вимірювань")
    parser.add_argument("--label", choices=["before", "after"], default="after")
    args = parser.parse_args()
    executable = ROOT / ".runtime/llama/llama-server.exe"
    model = ROOT / ".runtime/Qwen3-4B-Q4_K_M.gguf"
    if not executable.exists() or not model.exists():
        raise SystemExit("Спочатку виконайте: python lab4/tools/prepare_runtime.py")
    layers, flash = (28, "off") if args.label == "before" else (99, "on")
    command = [str(executable), "-m", str(model), "--alias", "game-bug-qwen3", "--host", "127.0.0.1",
               "--port", "8080", "-c", "8192", "-np", "2", "-ngl", str(layers), "-fa", flash,
               "--jinja", "--no-context-shift", "--metrics", "--reasoning", "off"]
    children = []
    log = (ROOT / f".runtime/{args.label}.log").open("w", encoding="utf-8")
    try:
        children.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT))
        for attempt in range(90):
            if children[0].poll() is not None:
                raise SystemExit("Модель не запустилася. Перевірте журнал у .runtime.")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2):
                    break
            except Exception:
                time.sleep(1)
        else:
            raise SystemExit("Модель не стала готовою протягом 90 секунд.")
        if not args.runtime_only:
            children.append(subprocess.Popen([sys.executable, str(ROOT / "lab4/app/server.py")]))
            print("Застосунок: http://127.0.0.1:8000", flush=True)
        print(f"Конфігурація: {args.label}; Ctrl+C — завершити.", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(1)
    except KeyboardInterrupt:
        print("Зупиняємо застосунок і модель…")
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        log.close()
