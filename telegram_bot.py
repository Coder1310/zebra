from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message


ROOT_DIR = Path(__file__).resolve().parent
LOG_DIR = ROOT_DIR / "data" / "logs"


@dataclass
class RunCfg:
  agents: int = 1000
  houses: int = 6
  days: int = 200
  share: str = "meet"
  noise: float = 0.2
  seed: int | None = None
  t: int = 500


def _parse_kv(tokens: list[str]) -> dict[str, str]:
  out: dict[str, str] = {}
  for t in tokens:
    if "=" not in t:
      continue
    k, v = t.split("=", 1)
    k = k.strip().lower()
    v = v.strip()
    if k:
      out[k] = v
  return out


def _parse_run_args(text: str) -> RunCfg:
  tokens = [t for t in text.strip().split() if t]
  cfg = RunCfg()

  kv = _parse_kv(tokens)
  if "agents" in kv:
    cfg.agents = int(kv["agents"])
  if "houses" in kv:
    cfg.houses = int(kv["houses"])
  if "days" in kv:
    cfg.days = int(kv["days"])
  if "share" in kv:
    cfg.share = kv["share"]
  if "noise" in kv:
    cfg.noise = float(kv["noise"])
  if "seed" in kv:
    cfg.seed = int(kv["seed"])
  if "t" in kv:
    cfg.t = int(kv["t"])

  pos = [t for t in tokens if "=" not in t]
  if pos:
    try:
      if len(pos) >= 1:
        cfg.agents = int(pos[0])
      if len(pos) >= 2:
        cfg.houses = int(pos[1])
      if len(pos) >= 3:
        cfg.days = int(pos[2])
      if len(pos) >= 4:
        cfg.share = pos[3]
      if len(pos) >= 5:
        cfg.noise = float(pos[4])
      if len(pos) >= 6:
        cfg.seed = int(pos[5])
      if len(pos) >= 7:
        cfg.t = int(pos[6])
    except Exception:
      pass

  return cfg


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
  r = requests.post(url, json=payload, timeout=timeout)
  r.raise_for_status()
  data = r.json()
  if not isinstance(data, dict):
    raise RuntimeError(f"bad json from {url}: {data}")
  return data


def _create_session(api: str, cfg: RunCfg) -> str:
  payload: dict[str, Any] = {
    "agents": cfg.agents,
    "houses": cfg.houses,
    "days": cfg.days,
    "share": cfg.share,
    "noise": cfg.noise,
  }
  if cfg.seed is not None:
    payload["seed"] = cfg.seed

  last_err: Exception | None = None
  for path in ("/session/create", "/session"):
    try:
      data = _post_json(f"{api}{path}", payload, timeout=30.0)
      sid = data.get("session_id")
      if isinstance(sid, str) and sid:
        return sid
      raise RuntimeError(f"no session_id in response: {data}")
    except Exception as e:
      last_err = e

  raise RuntimeError(f"cannot create session, last error: {last_err}")


def _start_session(api: str, sid: str, timeout: float) -> dict[str, Any]:
  last_err: Exception | None = None
  for path in (f"/session/{sid}/run", f"/session/{sid}/start"):
    try:
      r = requests.post(f"{api}{path}", timeout=timeout)
      r.raise_for_status()
      data = r.json()
      if not isinstance(data, dict):
        raise RuntimeError(f"bad json from {path}: {data}")
      return data
    except Exception as e:
      last_err = e
  raise RuntimeError(f"cannot start session, last error: {last_err}")


def _ensure_file(path: str) -> Path:
  p = Path(path)
  if not p.is_absolute():
    p = (ROOT_DIR / p).resolve()
  if not p.exists():
    raise FileNotFoundError(str(p))
  return p


def _count_lines(path: Path, limit: int = 2_000_000) -> int:
  n = 0
  with path.open("rb") as f:
    for _ in f:
      n += 1
      if n >= limit:
        break
  return n


def _pick_t(events: Path, requested_t: int) -> int:
  # events: csv with header, so lines-1 = number of events
  lines = _count_lines(events)
  events_n = max(0, lines - 1)
  if events_n <= 0:
    return max(1, requested_t)
  return max(1, min(requested_t, events_n))


def _run_process_log(metrics: Path, events: Path, out_dir: Path, t: int) -> None:
  out_dir.mkdir(parents=True, exist_ok=True)
  cmd = [
    sys.executable, "-m", "analysis.process_log",
    "--metrics", str(metrics),
    "--events", str(events),
    "--t", str(t),
    "--out_dir", str(out_dir),
  ]
  r = subprocess.run(cmd, text=True, capture_output=True)
  if r.returncode != 0:
    stdout_tail = (r.stdout or "")[-2000:]
    stderr_tail = (r.stderr or "")[-2000:]
    raise RuntimeError(
      f"process_log failed rc={r.returncode}\n"
      f"cmd={' '.join(cmd)}\n"
      f"stdout_tail:\n{stdout_tail}\n"
      f"stderr_tail:\n{stderr_tail}"
    )


def _zip_awareness(out_dir: Path, sid: str) -> Path:
  zip_path = out_dir / f"awareness_{sid}.zip"
  summary_path = out_dir / f"game_{sid}_summary.yaml"

  with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(out_dir.glob("awareness-*.csv")):
      z.write(p, arcname=p.name)
    for p in sorted(out_dir.glob("awareness-*.yaml")):
      z.write(p, arcname=p.name)
    if summary_path.exists():
      z.write(summary_path, arcname=summary_path.name)

  return zip_path


async def cmd_help(message: Message) -> None:
  txt = (
    "Команды:\n"
    "/run agents houses days share noise seed t\n"
    "/run agents = 1000 houses = 6 days = 200 share = meet noise = 0.2 seed = 1 t = 500\n\n"
    "Примеры:\n"
    "/run 50 6 50 meet 0.2\n"
    "/run 50 6 50 meet 0.2 t = 200\n"
  )
  await message.answer(txt)


async def cmd_run(message: Message, bot: Bot) -> None:
  api = os.getenv("ZEBRA_API", "http://127.0.0.1:8000")
  text = message.text or ""
  args_text = text.replace("/run", "", 1).strip()
  cfg = _parse_run_args(args_text)

  await message.answer(
    f"Запуск: agents = {cfg.agents} houses = {cfg.houses} days = {cfg.days} share = {cfg.share} noise = {cfg.noise} seed = {cfg.seed} t = {cfg.t}"
  )

  async def job() -> None:
    try:
      sid = await asyncio.to_thread(_create_session, api, cfg)
      await bot.send_message(message.chat.id, f"session = {sid} стартую")

      data = await asyncio.to_thread(_start_session, api, sid, 1800.0)

      csv_path = data.get("csv")
      metrics_path = data.get("metrics")
      if not isinstance(csv_path, str) or not isinstance(metrics_path, str):
        raise RuntimeError(f"server ответил без путей csv/metrics: {data}")

      events = await asyncio.to_thread(_ensure_file, csv_path)
      metrics = await asyncio.to_thread(_ensure_file, metrics_path)

      t_eff = await asyncio.to_thread(_pick_t, events, cfg.t)

      out_dir = LOG_DIR / f"bot_{sid}"
      await asyncio.to_thread(_run_process_log, metrics, events, out_dir, t_eff)

      summary = out_dir / f"game_{sid}_summary.yaml"
      if not summary.exists():
        raise FileNotFoundError(str(summary))

      aw_zip = await asyncio.to_thread(_zip_awareness, out_dir, sid)

      await bot.send_message(message.chat.id, f"session={sid} готово, отправляю файлы (t={t_eff})")

      await bot.send_document(message.chat.id, FSInputFile(str(metrics), filename=metrics.name))
      await bot.send_document(message.chat.id, FSInputFile(str(summary), filename=summary.name))

      if aw_zip.stat().st_size <= 45 * 1024 * 1024:
        await bot.send_document(message.chat.id, FSInputFile(str(aw_zip), filename=aw_zip.name))
      else:
        await bot.send_message(
          message.chat.id,
          f"awareness zip слишком большой ({aw_zip.stat().st_size / (1024*1024):.1f} MB), не отправляю"
        )

      await bot.send_message(message.chat.id, f"Готово: session={sid}")
    except Exception:
      err = traceback.format_exc()
      await bot.send_message(message.chat.id, f"Ошибка:\n{err[-3500:]}")

  asyncio.create_task(job())


def main() -> None:
  token = os.getenv("TG_TOKEN", "").strip()
  if not token:
    raise SystemExit("TG_TOKEN пуст. export TG_TOKEN=...")

  dp = Dispatcher()

  @dp.message(Command("help"))
  async def _h(message: Message) -> None:
    await cmd_help(message)

  @dp.message(Command("run"))
  async def _r(message: Message, bot: Bot) -> None:
    await cmd_run(message, bot)

  bot = Bot(token=token)
  asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
  main()
