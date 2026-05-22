"""Background workers — arq + Redis.

Two job kinds:
- `run_discovery`  : Stage 1-5 of the TrendHunter funnel (Exa + Claude Haiku)
- `run_research`   : full research engine (Parallel + Exa-deep + Claude Sonnet)

Run the worker with:
    cd apps/api && arq app.workers.settings.WorkerSettings
"""
