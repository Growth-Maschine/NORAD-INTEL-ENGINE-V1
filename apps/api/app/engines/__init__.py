"""External engine clients — thin SDK wrappers with retry + cost logging.

Three pipes used by the NORAD pipeline:

- `exa_client`      — Exa (search + /contents) — drives discovery + deep read
- `claude_client`   — Anthropic Claude (Haiku for rank, Sonnet for synth)
- `parallel_client` — Parallel Web (agentic research task with output schema)

Each client is a lazy singleton (instantiated on first call). Each logs every
API call to the `engine_calls` table for cost + latency visibility.
"""
from app.engines.claude_client import (
    ClaudeClient,
    ClaudeMessage,
    ClaudeResponse,
    get_claude_client,
)
from app.engines.exa_client import (
    ExaClient,
    ExaContent,
    ExaSearchResult,
    get_exa_client,
)
from app.engines.logging import log_claude_call, log_exa_call, log_parallel_call
from app.engines.parallel_client import (
    ParallelClient,
    ParallelTaskResponse,
    get_parallel_client,
)

__all__ = [
    "ClaudeClient",
    "ClaudeMessage",
    "ClaudeResponse",
    "ExaClient",
    "ExaContent",
    "ExaSearchResult",
    "ParallelClient",
    "ParallelTaskResponse",
    "get_claude_client",
    "get_exa_client",
    "get_parallel_client",
    "log_claude_call",
    "log_exa_call",
    "log_parallel_call",
]
