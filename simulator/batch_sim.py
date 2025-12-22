import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional


@dataclass
class Strategy:
  p_left: float
  p_right: float
  p_home: float
  p_share: float


@dataclass
class Agent:
  agent_id: str
  idx: int
  house_id: int
  location: int
  drink: str
  smokes: str
  pet: str
  strategy: Strategy


@dataclass
class Belief:
  houses: Dict[int, int]
  drinks: Dict[int, str]
  smokes: Dict[int, str]
  pets: Dict[int, str]


def read_zebra_init(path: str) -> List[Tuple[int, str, str, str, str]]:
  rows: List[Tuple[int, str, str, str, str]] = []
  with open(path, "r", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for r in reader:
      house_id = int(r["H"])
      drink = r["D"]
      smokes = r["S"]
      pet = r["P"]
      agent_id = r["I"]
      rows.append((house_id, agent_id, drink, smokes, pet))
  rows.sort(key=lambda x: x[0])
  return rows


def read_strategies(path: str) -> Dict[str, Strategy]:
  out: Dict[str, Strategy] = {}
  with open(path, "r", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for r in reader:
      agent_id = r["I"]
      p_left = float(r["PLeft"])
      p_right = float(r["PRight"])
      p_home = float(r["PHome"])
      p_share = 1.0
      out[agent_id] = Strategy(p_left=p_left, p_right=p_right, p_home=p_home, p_share=p_share)
  return out


def sample_direction(s: Strategy, rng: random.Random) -> str:
  x = rng.random()
  if x < s.p_left:
    return "left"
  x -= s.p_left
  if x < s.p_right:
    return "right"
  return "home"


def neighbor_left(h: int, n_houses: int) -> int:
  return ((h - 2) % n_houses) + 1


def neighbor_right(h: int, n_houses: int) -> int:
  return (h % n_houses) + 1


def init_beliefs(agents: List[Agent]) -> List[Belief]:
  beliefs: List[Belief] = []
  for a in agents:
    b = Belief(houses={}, drinks={}, smokes={}, pets={})
    b.houses[a.idx] = a.house_id
    b.drinks[a.idx] = a.drink
    b.smokes[a.idx] = a.smokes
    b.pets[a.idx] = a.pet
    beliefs.append(b)
  return beliefs


def merge_beliefs(dst: Belief, src: Belief) -> None:
  dst.houses.update(src.houses)
  dst.drinks.update(src.drinks)
  dst.smokes.update(src.smokes)
  dst.pets.update(src.pets)


def learn_direct(dst: Belief, other: Agent) -> None:
  dst.houses[other.idx] = other.house_id
  dst.drinks[other.idx] = other.drink
  dst.smokes[other.idx] = other.smokes
  dst.pets[other.idx] = other.pet


def calc_sa(b: Belief, n_agents: int) -> float:
  total = 4 * n_agents
  known = len(b.houses) + len(b.drinks) + len(b.smokes) + len(b.pets)
  return known / total if total > 0 else 0.0


def run_sim(
  agents: List[Agent],
  days: int,
  rng: random.Random,
  share_mode: str,
  log_path: Optional[str],
  sa_path: Optional[str],
) -> None:
  n_agents = len(agents)
  n_houses = max(a.house_id for a in agents) if agents else 0

  beliefs = init_beliefs(agents)

  log_rows: List[List] = []
  sa_rows: List[List] = []
  event_id = 0

  for day in range(1, days + 1):
    old_locations = [a.location for a in agents]

    for a in agents:
      direction = sample_direction(a.strategy, rng)

      if direction == "left":
        a.location = neighbor_left(a.location, n_houses)
      elif direction == "right":
        a.location = neighbor_right(a.location, n_houses)
      else:
        a.location = a.location

      event_id += 1
      if log_path is not None:
        log_rows.append([event_id, day, "visit", a.agent_id, old_locations[a.idx], a.location, 1])

    house_to_agents: Dict[int, List[int]] = {}
    for a in agents:
      house_to_agents.setdefault(a.location, []).append(a.idx)

    for _, idxs in house_to_agents.items():
      if len(idxs) < 2:
        continue

      for i in idxs:
        for j in idxs:
          if i == j:
            continue
          learn_direct(beliefs[i], agents[j])

      if share_mode == "meet":
        for i in idxs:
          for j in idxs:
            if i == j:
              continue
            if rng.random() <= agents[i].strategy.p_share:
              merge_beliefs(beliefs[i], beliefs[j])

    if sa_path is not None:
      avg_sa = sum(calc_sa(beliefs[i], n_agents) for i in range(n_agents)) / n_agents
      sa_rows.append([day, avg_sa])

  if log_path is not None:
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
      w = csv.writer(f, delimiter=";")
      w.writerow(["event_id", "day", "event", "who", "from", "to", "success"])
      w.writerows(log_rows)

  if sa_path is not None:
    p = Path(sa_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
      w = csv.writer(f, delimiter=";")
      w.writerow(["day", "avg_sa"])
      w.writerows(sa_rows)


def build_agents(
  n_agents: int,
  seed: int,
  zebra_init: str,
  zebra_strat: str,
) -> List[Agent]:
  rng = random.Random(seed)

  if n_agents == 6 and Path(zebra_init).exists() and Path(zebra_strat).exists():
    init_rows = read_zebra_init(zebra_init)
    strat = read_strategies(zebra_strat)

    agents: List[Agent] = []
    for idx, (house_id, agent_id, drink, smokes, pet) in enumerate(init_rows):
      s = strat.get(agent_id, Strategy(1/3, 1/3, 1/3, 1.0))
      agents.append(
        Agent(
          agent_id=agent_id,
          idx=idx,
          house_id=house_id,
          location=house_id,
          drink=drink,
          smokes=smokes,
          pet=pet,
          strategy=s,
        )
      )
    return agents

  agents = []
  for i in range(n_agents):
    agents.append(
      Agent(
        agent_id=f"a{i}",
        idx=i,
        house_id=i + 1,
        location=i + 1,
        drink=f"d{i%6}",
        smokes=f"s{i%6}",
        pet=f"p{i%6}",
        strategy=Strategy(1/3, 1/3, 1/3, 1.0),
      )
    )
  return agents


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--agents", type=int, default=6)
  ap.add_argument("--days", type=int, default=200)
  ap.add_argument("--seed", type=int, default=1)
  ap.add_argument("--share", choices=["none", "meet"], default="meet")
  ap.add_argument("--log", type=int, default=1)
  ap.add_argument("--sa", type=int, default=1)
  args = ap.parse_args()

  agents = build_agents(
    n_agents=args.agents,
    seed=args.seed,
    zebra_init="data/zebra-01.csv",
    zebra_strat="data/ZEBRA-strategies.csv",
  )

  log_path = "data/logs/batch_log.csv" if args.log else None
  sa_path = "data/logs/batch_sa.csv" if args.sa else None

  rng = random.Random(args.seed)
  run_sim(
    agents=agents,
    days=args.days,
    rng=rng,
    share_mode=args.share,
    log_path=log_path,
    sa_path=sa_path,
  )

  print("ok")


if __name__ == "__main__":
  main()
