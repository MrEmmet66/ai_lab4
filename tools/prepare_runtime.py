"""Завантажує модель і llama.cpp для запуску застосунку. Python 3.11+."""
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / ".runtime"
FILES = {
    "runtime": "b12328",
    "runtime_url": "https://github.com/ggml-org/llama.cpp/releases/download/b12328/llama-b12328-bin-win-vulkan-x64.zip",
    "runtime_sha256": "sha256:8c35cf877f1f797d48b9c1610c64593d0dca17df1739e634373537fc799cdb0b",
    "model_url": "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf",
    "model_revision": "bc640142c66e1fdd12af0bd68f40445458f3869b",
    "model_sha256": "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
    "model_bytes": 2497280256
}


def download(url, destination):
    if destination.exists():
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Завантаження: {destination.name}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
        while chunk := response.read(4 * 1024 * 1024):
            output.write(chunk)
    temporary.replace(destination)


def verify(file, expected):
    with file.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != expected.removeprefix("sha256:"):
        raise SystemExit(f"Контрольна сума не збігається: {file.name}. Видаліть цей файл і повторіть завантаження.")


def main():
    parser = argparse.ArgumentParser(description="Підготовка локальної моделі")
    parser.add_argument("--check-only", action="store_true", help="Лише перевірити вже завантажені файли")
    args = parser.parse_args()
    DEST.mkdir(exist_ok=True)
    archive = DEST / "llama-vulkan.zip"
    model = DEST / "Qwen3-4B-Q4_K_M.gguf"
    if not args.check_only:
        with ThreadPoolExecutor(2) as executor:
            futures = [executor.submit(download, FILES["runtime_url"], archive), executor.submit(download, FILES["model_url"], model)]
            for future in futures:
                future.result()
    if not archive.exists() or not model.exists():
        raise SystemExit("Файлів немає. Запустіть prepare_runtime.py без --check-only.")
    verify(archive, FILES["runtime_sha256"])
    verify(model, FILES["model_sha256"])
    executable = DEST / "llama/llama-server.exe"
    if not args.check_only and not executable.exists():
        with zipfile.ZipFile(archive) as source:
            source.extractall(DEST / "llama")
    if not executable.exists():
        raise SystemExit("Програму llama.cpp ще не розпаковано. Запустіть підготовку без --check-only.")
    if not args.check_only:
        (DEST / "manifest.json").write_text(json.dumps(FILES, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Модель і llama.cpp готові. Запуск: python lab4/app/run.py")


if __name__ == "__main__":
    main()
