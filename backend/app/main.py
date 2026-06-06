"""
goku-studio — Studio domain API service.

Owns: agent_definitions, workflows, tools, MCP servers, knowledge,
      external_memory_sources, IRA, improvement_proposals, prompt_experiments.

Does NOT own: tasks, conversations, approvals, users, tenants, channels.
Core runtime (task execution, ReAct loop) lives in goku-core.

During the monorepo transition period, Studio is also mounted inside the
monorepo's main.py (app/routers/studio). This standalone main.py is used
only when Studio is deployed as a separate service.
"""
from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Lazy: only import Studio router + Studio models ───────────────────────────
# This import boundary is the whole point of the extraction.
from app.routers.studio import router as studio_router  # type: ignore[import]

app = FastAPI(
    title="Goku Studio API",
    version="1.0.0",
    description="AI application construction API — agents, workflows, tools, MCP, knowledge.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:5106").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Studio API is served under /api/studio/v1/  (Phase 4 URL split)
# Legacy /api/v1/ aliases are registered in the monorepo's main.py
app.include_router(studio_router, prefix="/api/studio/v1")
