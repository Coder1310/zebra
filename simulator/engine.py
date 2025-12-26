from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Trip:
  active: bool = False
  dst: int = 1
  remaining: int = 0


@dataclass
class Agent:
  name: str
  house_id: int
  location: int
  pet_id: int
  trip: Trip
  known: int = 0


def _clamp_int(x: int, lo: int, hi: int) -> int:
  if x < lo:
    return lo
  if x > hi:
    return hi
  return x


def _norm3(a: int, b: int, c: int) -> tuple[int, int, int]:
  s = max(0, a) + max(0, b) + max(0, c)
  if s <= 0:
    return (33, 33, 34)
  aa = int(round(100.0 * max(0, a) / s))
  bb = int(round(100.0 * max(0, b) / s))
  cc = 100 - aa - bb
  if cc < 0:
    cc = 0
    if aa + bb > 0:
      k = 100.0 / (aa + bb)
      aa = int(round(aa * k))
      bb = 100 - aa
    else:
      aa, bb, cc = 33, 33, 34
  return (aa, bb, cc)


def _pick_weighted(rng: random.Random, items: list[tuple[str, int]]) -> str:
  total = 0
  for _, w in items:
    total += max(0, int(w))
  if total <= 0:
    return items[-1][0]
  r = rng.random() * total
  acc = 0
  for val, w in items:
    acc += max(0, int(w))
    if r <= acc:
      return val
  return items[-1][0]


def _wrap_house(x: int, houses: int) -> int:
  while x < 1:
    x += houses
  while x > houses:
    x -= houses
  return x


def _write_xml(xml_path: Path, session_id: str, events: list[dict[str, Any]]) -> None:
  parts: list[str] = []
  parts.append(f'<game session = "{session_id}">')
  for e in events:
    attrs = " ".join(f'{k} = "{str(v)}"' for k, v in e.items())
    parts.append(f"  <event {attrs} />")
  parts.append("</game>\n")
  xml_path.write_text("\n".join(parts), encoding = "utf-8")


def run_session(session_id: str, cfg: dict[str, Any], log_dir: Path) -> dict[str, Any]:
  log_dir.mkdir(parents=True, exist_ok=True)

  agents_n = int(cfg.get("agents", 6))
  houses = int(cfg.get("houses", 6))
  days = int(cfg.get("days", 200))

  share = str(cfg.get("share", "none"))
  noise = float(cfg.get("noise", 0.0))
  seed = cfg.get("seed", None)

  mt_who = cfg.get("mt_who", None)
  mt_strategy = cfg.get("mt_strategy", None)

  if seed is None:
    seed = int(session_id[:8], 16) & 0x7FFFFFFF
  rng = random.Random(seed)

  total_facts = houses * 5

  agents: list[Agent] = []
  for i in range(agents_n):
    home = (i % houses) + 1
    agents.append(
      Agent(
        name = f"a{i}",
        house_id = home,
        location = home,
        pet_id = (i % houses) + 1,
        trip = Trip(False, home, 0),
        known = 0,
      )
    )

  def mt_for(a: Agent) -> dict[str, int] | None:
    if mt_who is None or mt_strategy is None:
      return None
    if a.name != mt_who:
      return None
    try:
      s = dict(mt_strategy)
    except Exception:
      return None
    return {
      "p_left": int(s.get("p_left", 33)),
      "p_right": int(s.get("p_right", 33)),
      "p_home": int(s.get("p_home", 34)),
      "p_house_exch": int(s.get("p_house_exch", 0)),
      "p_pet_exch": int(s.get("p_pet_exch", 0)),
    }

  event_rows: list[list[str]] = []
  xml_events: list[dict[str, Any]] = []
  eid = 0

  def log_event(day: int, kind: str, *cols: Any) -> None:
    nonlocal eid
    eid += 1
    row = [str(eid), str(day), kind]
    for x in cols:
      row.append("" if x is None else str(x))
    while len(row) < 10:
      row.append("")
    event_rows.append(row[:10])

    xml_events.append(
      {"id": eid, "day": day, "type": kind, "a": row[3] if len(row) > 3 else ""}
    )

  metrics_path = log_dir / f"metrics_{session_id}.csv"
  events_path = log_dir / f"game_{session_id}.csv"
  xml_path = log_dir / f"game_{session_id}.xml"

  with metrics_path.open("w", newline = "", encoding = "utf-8") as mf:
    w = csv.writer(mf)
    header = ["day"] + [a.name for a in agents]
    w.writerow(header)

    for day in range(1, days + 1):
      for a in agents:
        if a.trip.active:
          a.trip.remaining -= 1
          if a.trip.remaining <= 0:
            a.location = a.trip.dst
            a.trip.active = False
            log_event(day, "FinishTrip", a.name, a.location)
            a.known = min(total_facts, a.known + 1)
          continue

        strat = mt_for(a)
        if strat is None:
          p_left, p_right, p_home = (33, 33, 34)
          p_house_exch = 10
          p_pet_exch = 10
        else:
          p_left, p_right, p_home = _norm3(strat["p_left"], strat["p_right"], strat["p_home"])
          p_house_exch = _clamp_int(strat["p_house_exch"], 0, 100)
          p_pet_exch = _clamp_int(strat["p_pet_exch"], 0, 100)

        did_exch = False

        if rng.randint(1, 100) <= p_house_exch:
          partner = rng.randrange(agents_n)
          b = agents[partner]
          a.house_id, b.house_id = b.house_id, a.house_id
          log_event(day, "changeHouse", a.name, b.name, a.location)
          a.known = min(total_facts, a.known + 2)
          did_exch = True

        if rng.randint(1, 100) <= p_pet_exch:
          partner = rng.randrange(agents_n)
          b = agents[partner]
          a.pet_id, b.pet_id = b.pet_id, a.pet_id
          log_event(day, "changePet", a.name, b.name, a.location)
          a.known = min(total_facts, a.known + 2)
          did_exch = True

        if did_exch and rng.random() < 0.4:
          pass
        else:
          direction = _pick_weighted(
            rng,
            [("left", p_left), ("right", p_right), ("home", p_home)],
          )

          src = a.location
          if direction == "home":
            dst = a.house_id
          elif direction == "left":
            dst = _wrap_house(a.location - 1, houses)
          else:
            dst = _wrap_house(a.location + 1, houses)

          if dst != src:
            a.trip.active = True
            a.trip.dst = dst
            a.trip.remaining = 1
            log_event(day, "startTrip", a.name, src, dst, 1)
            a.known = min(total_facts, a.known + 1)

      if share == "meet":
        groups: dict[int, list[Agent]] = {}
        for a in agents:
          groups.setdefault(a.location, []).append(a)

        for loc, group in groups.items():
          if len(group) < 2:
            continue
          best = max(x.known for x in group)
          for x in group:
            x.known = best

          if noise > 0.0:
            for x in group:
              if rng.random() < noise:
                if x.known > 0:
                  x.known -= 1

      row = [day]
      for a in agents:
        m1 = a.known / float(total_facts)
        row.append(f"{m1:.6f}")
      w.writerow(row)

  with events_path.open("w", newline = "", encoding = "utf-8") as ef:
    ef.write("eventID;day;event;a;b;c;d;e;f;g\n")
    for r in event_rows:
      ef.write(";".join(r) + "\n")

  _write_xml(xml_path, session_id = session_id, events = xml_events)

  return {
    "csv": events_path,
    "xml": xml_path,
    "metrics": metrics_path,
    "finished_at": time.time(),
  }
