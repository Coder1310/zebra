import argparse
import csv
import json
import os
import random
import re
import time
from dataclasses import dataclass
from glob import glob

import requests


@dataclass(frozen=True)
class Strategy:
  p_left: int
  p_right: int
  p_home: int
  p_house_exch: int
  p_pet_exch: int

  def as_dict(self) -> dict:
    return {
      "p_left": self.p_left,
      "p_right": self.p_right,
      "p_home": self.p_home,
      "p_house_exch": self.p_house_exch,
      "p_pet_exch": self.p_pet_exch,
    }


def _list_metrics_files(logs_dir: str) -> list[str]:
  patterns = [
    os.path.join(logs_dir, "metrics_*.csv"),
    os.path.join(logs_dir, "metrics-*.csv"),
    os.path.join(logs_dir, "metrics*.csv"),
  ]
  files: list[str] = []
  for p in patterns:
    files.extend(glob(p))
  files = sorted(set(files), key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0.0)
  return files


def _detect_delimiter(path: str) -> str:
  with open(path, "r", encoding="utf-8") as f:
    head = f.readline()
  if head.count(";") >= head.count(","):
    return ";"
  return ","


def _read_metric_series(metrics_csv: str, who: str) -> tuple[list[int], list[float]]:
  delim = _detect_delimiter(metrics_csv)
  days: list[int] = []
  vals: list[float] = []
  with open(metrics_csv, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter=delim)
    if not reader.fieldnames or "day" not in reader.fieldnames:
      raise RuntimeError(f"bad metrics header: {reader.fieldnames}")
    if who not in reader.fieldnames:
      raise RuntimeError(f"cannot find '{who}' column in: {reader.fieldnames[:10]} ...")
    for row in reader:
      days.append(int(float(row["day"])))
      vals.append(float(row[who]))
  return days, vals


def _score(vals: list[float], mode: str, tail: int) -> float:
  if not vals:
    return 0.0
  if mode == "final":
    return float(vals[-1])
  if mode == "mean_tail":
    k = min(tail, len(vals))
    return float(sum(vals[-k:]) / k)
  raise ValueError(mode)


def _parse_kv_text(text: str) -> dict:
  out: dict[str, str] = {}
  for m in re.finditer(r"(\w+)\s*=\s*([^\s]+)", text):
    out[m.group(1)] = m.group(2)
  return out


def _create_session(api: str, cfg: dict) -> str:
  r = requests.post(f"{api}/session/create", json=cfg, timeout=60)
  r.raise_for_status()

  sid = None
  try:
    data = r.json()
    sid = data.get("session_id") or data.get("session") or data.get("sid") or data.get("id")
  except Exception:
    pass

  if not sid:
    t = r.text.strip()
    if t.startswith("{") and t.endswith("}"):
      try:
        data = json.loads(t)
        sid = data.get("session_id") or data.get("session") or data.get("sid") or data.get("id")
      except Exception:
        sid = None

  if not sid:
    sid = r.text.strip().strip('"').strip("'")

  if not sid:
    raise RuntimeError(f"cannot parse session id: {r.text}")

  return str(sid)


def _try_get_json(resp: requests.Response) -> dict:
  try:
    data = resp.json()
    if isinstance(data, dict):
      return data
  except Exception:
    pass
  t = resp.text if isinstance(resp.text, str) else ""
  kv = _parse_kv_text(t)
  if kv:
    return kv
  return {}


def _extract_paths(info: dict) -> tuple[str | None, str | None, str | None, str | None]:
  status = None
  metrics = None
  csv_path = None
  xml_path = None

  if isinstance(info, dict):
    status = info.get("status")
    metrics = info.get("metrics")
    csv_path = info.get("csv")
    xml_path = info.get("xml")

  def _norm(x: str | None) -> str | None:
    if not isinstance(x, str):
      return None
    x = x.strip()
    return x if x else None

  return _norm(status), _norm(metrics), _norm(csv_path), _norm(xml_path)


def _find_new_metrics_file(logs_dir: str, sid: str, t_start: float, prev_set: set[str]) -> str | None:
  files = _list_metrics_files(logs_dir)

  cand_sid = []
  cand_any = []
  for f in files:
    try:
      mt = os.path.getmtime(f)
    except OSError:
      continue
    if mt < t_start - 0.2:
      continue
    if f in prev_set:
      continue
    if sid in os.path.basename(f):
      cand_sid.append(f)
    else:
      cand_any.append(f)

  if cand_sid:
    return max(cand_sid, key=os.path.getmtime)
  if cand_any:
    return max(cand_any, key=os.path.getmtime)
  return None


def _wait_run_done(api: str, sid: str, logs_dir: str, wait_sec: float) -> tuple[str, str | None, str | None]:
  prev_files = set(_list_metrics_files(logs_dir))
  t_start = time.time()

  last_status = None
  last_deadline = None
  last_info = None

  while time.time() - t_start < wait_sec:
    try:
      r = requests.post(f"{api}/session/{sid}/run", timeout=60)
      r.raise_for_status()
      info = _try_get_json(r)
      last_info = info
      status, metrics, csv_path, xml_path = _extract_paths(info)

      if status:
        last_status = status
      if isinstance(info, dict) and "deadline" in info:
        try:
          last_deadline = float(info["deadline"])
        except Exception:
          last_deadline = None

      if metrics and os.path.exists(metrics):
        return metrics, csv_path, xml_path
      if metrics and os.path.exists(os.path.join(logs_dir, os.path.basename(metrics))):
        return os.path.join(logs_dir, os.path.basename(metrics)), csv_path, xml_path

      if metrics and (status in (None, "done", "ok", "finished", "complete")):
        if os.path.exists(metrics):
          return metrics, csv_path, xml_path

      if (status in ("done", "ok", "finished", "complete")) and metrics:
        return metrics, csv_path, xml_path

      new_m = _find_new_metrics_file(logs_dir, sid, t_start, prev_files)
      if new_m is not None:
        return new_m, csv_path, xml_path

    except Exception:
      new_m = _find_new_metrics_file(logs_dir, sid, t_start, prev_files)
      if new_m is not None:
        return new_m, None, None

    if last_deadline is not None:
      dt = max(0.05, min(1.0, last_deadline - time.time()))
      time.sleep(dt)
    else:
      time.sleep(0.2)

  raise RuntimeError(
    "run timeout\n"
    f"sid={sid}\n"
    f"last_status={last_status}\n"
    f"last_deadline={last_deadline}\n"
    f"last_info={last_info}\n"
    f"last_metrics_files={_list_metrics_files(logs_dir)[-5:]}\n"
  )


def _fix_sum_100(a: int, b: int, c: int) -> tuple[int, int, int]:
  a = max(0, min(100, a))
  b = max(0, min(100, b))
  c = max(0, min(100, c))
  s = a + b + c
  if s == 0:
    return 33, 33, 34
  a = int(round(a * 100 / s))
  b = int(round(b * 100 / s))
  c = 100 - a - b
  if c < 0:
    c = 0
    if a >= b:
      a = 100 - b
    else:
      b = 100 - a
  return a, b, c


def _sample_strategy(rng: random.Random) -> Strategy:
  x1 = rng.random()
  x2 = rng.random()
  x3 = rng.random()
  s = x1 + x2 + x3
  p_left = int(round(100 * x1 / s))
  p_right = int(round(100 * x2 / s))
  p_home = 100 - p_left - p_right
  p_left, p_right, p_home = _fix_sum_100(p_left, p_right, p_home)
  return Strategy(
    p_left=p_left,
    p_right=p_right,
    p_home=p_home,
    p_house_exch=rng.randint(0, 100),
    p_pet_exch=rng.randint(0, 100),
  )


def _write_yaml(path: str, data: dict) -> None:
  lines: list[str] = []
  for k, v in data.items():
    if isinstance(v, dict):
      lines.append(f"{k}:")
      for kk, vv in v.items():
        lines.append(f"  {kk}: {vv}")
    else:
      lines.append(f"{k}: {v}")
  with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--api", default="http://127.0.0.1:8000")
  ap.add_argument("--agents", type=int, default=1000)
  ap.add_argument("--houses", type=int, default=6)
  ap.add_argument("--days", type=int, default=200)
  ap.add_argument("--share", default="meet", choices=["none", "meet"])
  ap.add_argument("--noise", type=float, default=0.2)
  ap.add_argument("--who", default="a0")
  ap.add_argument("--iters", type=int, default=10)
  ap.add_argument("--seeds", default="1,2,3")
  ap.add_argument("--score", default="final", choices=["final", "mean_tail"])
  ap.add_argument("--tail", type=int, default=20)
  ap.add_argument("--wait", type=int, default=600)
  ap.add_argument("--out_dir", default="data/logs")
  ap.add_argument("--logs_dir", default="data/logs")
  ap.add_argument("--rng_seed", type=int, default=42)
  args = ap.parse_args()

  seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
  os.makedirs(args.out_dir, exist_ok=True)

  trials_csv = os.path.join(args.out_dir, "mt_trials.csv")
  best_yaml = os.path.join(args.out_dir, "mt_best.yaml")
  compare_png = os.path.join(args.out_dir, "mt_compare.png")

  rng = random.Random(args.rng_seed)

  def eval_strategy(strategy: Strategy | None) -> tuple[float, list[str], list[str]]:
    scores: list[float] = []
    sids: list[str] = []
    metrics_paths: list[str] = []

    for sd in seeds:
      cfg = {
        "agents": args.agents,
        "houses": args.houses,
        "days": args.days,
        "share": args.share,
        "noise": args.noise,
        "seed": sd,
      }
      if strategy is not None:
        cfg["mt_who"] = args.who
        cfg["mt_strategy"] = strategy.as_dict()

      sid = _create_session(args.api, cfg)
      metrics_path, _, _ = _wait_run_done(args.api, sid, args.logs_dir, float(args.wait))

      _, vals = _read_metric_series(metrics_path, args.who)
      scores.append(_score(vals, args.score, args.tail))
      sids.append(sid)
      metrics_paths.append(metrics_path)

    return float(sum(scores) / len(scores)), sids, metrics_paths

  baseline_score, baseline_sids, baseline_metrics = eval_strategy(None)

  best_strategy = _sample_strategy(rng)
  best_score, best_sids, best_metrics = eval_strategy(best_strategy)

  with open(trials_csv, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["kind", "score", "sids", "metrics", "p_left", "p_right", "p_home", "p_house_exch", "p_pet_exch"])
    w.writerow(["baseline", baseline_score, "|".join(baseline_sids), "|".join(baseline_metrics), "", "", "", "", ""])
    w.writerow([
      "trial0",
      best_score,
      "|".join(best_sids),
      "|".join(best_metrics),
      best_strategy.p_left,
      best_strategy.p_right,
      best_strategy.p_home,
      best_strategy.p_house_exch,
      best_strategy.p_pet_exch,
    ])

  for _ in range(args.iters):
    cand = _sample_strategy(rng)
    cand_score, cand_sids, cand_metrics = eval_strategy(cand)
    with open(trials_csv, "a", encoding="utf-8", newline="") as f:
      w = csv.writer(f)
      w.writerow([
        "trial",
        cand_score,
        "|".join(cand_sids),
        "|".join(cand_metrics),
        cand.p_left,
        cand.p_right,
        cand.p_home,
        cand.p_house_exch,
        cand.p_pet_exch,
      ])
    if cand_score > best_score:
      best_score = cand_score
      best_strategy = cand
      best_sids = cand_sids
      best_metrics = cand_metrics
      print(f"new best score={best_score:.4f} strat={best_strategy}")

  _write_yaml(best_yaml, {
    "who": args.who,
    "baseline_score": baseline_score,
    "best_score": best_score,
    "best_strategy": best_strategy.as_dict(),
    "baseline_sids": {"sids": "|".join(baseline_sids)},
    "best_sids": {"sids": "|".join(best_sids)},
  })

  try:
    import matplotlib.pyplot as plt
    d1, v1 = _read_metric_series(baseline_metrics[0], args.who)
    d2, v2 = _read_metric_series(best_metrics[0], args.who)
    plt.figure()
    plt.plot(d1, v1, label="baseline")
    plt.plot(d2, v2, label="mt_best")
    plt.xlabel("day")
    plt.ylabel("M1")
    plt.legend()
    plt.tight_layout()
    plt.savefig(compare_png, dpi=200)
    print(f"saved {compare_png}")
  except Exception as e:
    print(f"skip plot: {e}")

  print(f"saved {best_yaml}")
  print(f"saved {trials_csv}")


if __name__ == "__main__":
  main()
