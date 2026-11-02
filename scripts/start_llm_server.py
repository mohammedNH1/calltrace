"""Download (if needed) and start the local llama.cpp server for the analysis model.

Usage: python scripts/start_llm_server.py [--gpu-layers 99] [--ctx 8192]

The server runs until stopped. It needs no API key and only listens on localhost.
On a machine that is not Windows, install llama.cpp yourself and pass --binary.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download

from calltrace.config import PROJECT_ROOT, load_config

LLAMA_RELEASE = "b12034"
LLAMA_ZIP = f"llama-{LLAMA_RELEASE}-bin-win-vulkan-x64.zip"
LLAMA_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_RELEASE}/{LLAMA_ZIP}"


def ensure_binary(target_dir: Path) -> Path:
    """Fetch the pinned Windows Vulkan build, which needs no CUDA install."""
    binary = target_dir / "llama-server.exe"
    if not binary.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {LLAMA_URL}")
        with urllib.request.urlopen(LLAMA_URL, timeout=600) as response:
            zipfile.ZipFile(io.BytesIO(response.read())).extractall(target_dir)
    return binary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=None)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--ctx", type=int, default=16384)
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--device", default=None, help="for example Vulkan1; see llama-server --list-devices")
    args = parser.parse_args()

    settings = load_config()["llm"]
    models_dir = PROJECT_ROOT / "models"
    binary = args.binary or ensure_binary(models_dir / "llama-cpp")
    gguf = models_dir / "gguf" / settings["gguf_file"]
    if not gguf.exists():
        hf_hub_download(
            settings["model_id"],
            settings["gguf_file"],
            revision=settings["model_revision"],
            local_dir=gguf.parent,
        )

    command = [
        str(binary),
        "--model", str(gguf),
        "--host", "127.0.0.1",
        "--port", str(args.port),
        "--ctx-size", str(args.ctx),
        "--n-gpu-layers", str(args.gpu_layers),
        "--seed", str(settings["seed"]),
        "--jinja",
        "--reasoning", "off",  # thinking off: the answer is schema-constrained JSON
        "--parallel", "1",
    ]
    if args.device:
        command += ["--device", args.device]
    print(" ".join(command))
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
