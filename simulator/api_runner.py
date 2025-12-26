from __future__ import annotations

import argparse
import time
from typing import Any, Dict, Optional

import requests


def _as_sid(obj: Any) -> str:
  if isinstance(obj, dict) and "session_id" in obj:
    val = obj["session_id"]
    if isinstance(val, str):
      return val
    if isinstance(val, dict) and "session_id" in val and isinstance(val["session_id"], str):
      return val["session_id"]
  if isinstance(obj, str):
    return obj
  raise RuntimeError(f"cannot parse session_id from: {obj}")


def _pick_path(payload: Dict[str, Any], key: str) -> Optional[str]:
  if key not in payload:
    return None
  val = payload[key]
  if isinstance(val, str):
    return val
  if isinstance(val, dict) and "path" in val and isinstance(val["path"], str):
    return val["path"]
  return None


def _post_json(url: str, json_data: Dict[str, Any], timeout: float) -> Dict[str, Any]:
  r = requests.post(url, json = json_data, timeout = timeout)
  r.raise_for_status()
  data = r.json()
  if not isinstance(data, dict):
    raise RuntimeError(f"unexpected json at {url}: {data}")
  return data


def _create_session(api: str, cfg: Dict[str, Any]) -> str:
  last_err = None
  for path in ("/session/create", "/session"):
    try:
      data = _post_json(f"{api}{path}", cfg, timeout = 30.0)
      return _as_sid(data)
    except Exception as e:
      last_err = e
  raise RuntimeError(f"cannot create session, last error: {last_err}")


def _start_or_run(api: str, sid: str, timeout: float) -> Dict[str, Any]:
  last_err = None
  for path in (f"/session/{sid}/start", f"/session/{sid}/run"):
    try:
      r = requests.post(f"{api}{path}", timeout = timeout)
      r.raise_for_status()
      data = r.json()
      if not isinstance(data, dict):
        raise RuntimeError(f"unexpected json at {path}: {data}")
      return data
    except Exception as e:
      last_err = e
  raise RuntimeError(f"cannot start/run session, last error: {last_err}")


def main() -> None:
  p = argparse.ArgumentParser()
  p.add_argument("--api", default = "http://127.0.0.1:8000")
  p.add_argument("--agents", type = int, default = 6)
  p.add_argument("--houses", type = int, default = 6)
  p.add_argument("--days", type = int, default = 200)
  p.add_argument("--share", default = "none")
  p.add_argument("--noise", type = float, default = 0.0)
  p.add_argument("--seed", type = int, default = None)

  args = p.parse_args()

  cfg: Dict[str, Any] = {
    "agents": args.agents,
    "houses": args.houses,
    "days": args.days,
    "share": args.share,
    "noise": args.noise,
  }
  if args.seed is not None:
    cfg["seed"] = args.seed

  sid = _create_session(args.api, cfg)

  start_t = time.time()
  data = _start_or_run(args.api, sid, timeout = 600.0)
  _ = start_t

  csv_path = _pick_path(data, "csv")
  xml_path = _pick_path(data, "xml")
  metrics_path = _pick_path(data, "metrics")

  if csv_path is None or xml_path is None or metrics_path is None:
    raise RuntimeError(f"server did not return csv/xml/metrics paths: {data}")

  print(f"session = {sid}")
  print(f"csv = {csv_path}")
  print(f"xml = {xml_path}")
  print(f"metrics = {metrics_path}")


if __name__ == "__main__":
  main()
