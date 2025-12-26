from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from simulator.engine import run_session


ROOT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT_DIR / "data" / "logs"


class MTStrategy(BaseModel):
  model_config = ConfigDict(extra="forbid")

  p_left: int = Field(ge = 0, le = 100)
  p_right: int = Field(ge = 0, le = 100)
  p_home: int = Field(ge = 0, le = 100)
  p_house_exch: int = Field(ge = 0, le = 100)
  p_pet_exch: int = Field(ge = 0, le = 100)


class CreateSessionRequest(BaseModel):
  model_config = ConfigDict(extra = "allow")

  agents: int = Field(ge = 1, le = 20000, default = 6)
  houses: int = Field(ge = 2, le = 50, default = 6)
  days: int = Field(ge = 1, le = 20000, default = 200)

  share: str = Field(default = "none")
  noise: float = Field(ge = 0.0, le = 1.0, default = 0.0)
  seed: Optional[int] = None

  mt_who: Optional[str] = None
  mt_strategy: Optional[MTStrategy] = None


class CreateSessionResponse(BaseModel):
  session_id: str


class RunResponse(BaseModel):
  status: str
  session_id: str
  csv: str
  xml: str
  metrics: str
  finished_at: float


app = FastAPI(title = "Zebra SA Server")

_sessions: dict[str, dict[str, Any]] = {}


def _new_sid() -> str:
  return uuid.uuid4().hex[:12]


def _save_session(sid: str, cfg: dict[str, Any]) -> None:
  _sessions[sid] = {
    "created_at": time.time(),
    "cfg": cfg,
    "done": False,
    "files": None,
  }


def _normalize_cfg(req: CreateSessionRequest) -> dict[str, Any]:
  cfg = req.model_dump()
  if req.mt_strategy is not None:
    cfg["mt_strategy"] = req.mt_strategy.model_dump()
  return cfg


@app.get("/health")
def health() -> dict[str, str]:
  return {"status": "ok"}


@app.post("/session", response_model=CreateSessionResponse)
def create_session_alt(req: CreateSessionRequest) -> CreateSessionResponse:
  return create_session(req)


@app.post("/session/create", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
  LOG_DIR.mkdir(parents = True, exist_ok = True)
  sid = _new_sid()
  cfg = _normalize_cfg(req)
  _save_session(sid, cfg)
  return CreateSessionResponse(session_id = sid)


def _run_and_return(sid: str) -> RunResponse:
  if sid not in _sessions:
    raise HTTPException(status_code = 404, detail = "unknown session_id")

  s = _sessions[sid]
  if s["done"] and s["files"] is not None:
    files = s["files"]
    return RunResponse(
      status="done",
      session_id = sid,
      csv = str(files["csv"]),
      xml = str(files["xml"]),
      metrics = str(files["metrics"]),
      finished_at = float(files["finished_at"]),
    )

  cfg = dict(s["cfg"])
  files = run_session(session_id = sid, cfg = cfg, log_dir = LOG_DIR)

  s["done"] = True
  s["files"] = files

  return RunResponse(
    status = "done",
    session_id = sid,
    csv = str(files["csv"]),
    xml = str(files["xml"]),
    metrics = str(files["metrics"]),
    finished_at = float(files["finished_at"]),
  )


@app.post("/session/{sid}/run", response_model=RunResponse)
def run_session_endpoint(sid: str) -> RunResponse:
  return _run_and_return(sid)


@app.post("/session/{sid}/start", response_model=RunResponse)
def start_session_endpoint(sid: str) -> RunResponse:
  return _run_and_return(sid)
