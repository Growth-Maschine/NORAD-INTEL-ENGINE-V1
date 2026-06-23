"""Find a free TCP port for local dev servers."""
from __future__ import annotations

import socket


def find_free_port(*, start: int = 8000, max_tries: int = 100) -> int:
    for port in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free port in range {start}–{start + max_tries - 1}")
