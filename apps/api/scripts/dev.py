#!/usr/bin/env python3
"""Start FastAPI with reload on the first free port from 8000 upward."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from dev_port import find_free_port  # noqa: E402


def main() -> None:
    api_dir = Path(__file__).resolve().parents[1]
    os.chdir(api_dir)

    port = find_free_port(start=8000)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  NORAD API  →  {url}")
    print(f"  OpenAPI    →  {url}/docs\n")

    if port != 8000:
        print(
            f"  Note: port 8000 was busy — using {port}.\n"
            f"  Vite proxy targets 8000. Either stop the other API process, or add to apps/web/.env.local:\n"
            f"    VITE_API_URL={url}\n"
        )

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
    ]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
