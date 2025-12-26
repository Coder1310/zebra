import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Strategy:
  p_left: float
  p_right: float
  p_home: float
  p_house_exch: float
  p_pet_exch: float


@dataclass
class Trip:
  active: bool
  from_house: int
  to_house: int
  days_left: int
  start_event_id: int


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
  trip: Trip


@dataclass
class Belief:
  houses: Dict[int, int]
  drinks: Dict[int, str]
  smokes: Dict[int, str]
  pets: Dict[int, str]


@dataclass
class Domains:
  drinks: List[str]
  smokes: List[str]
  pets: List[str]


def _to_prob(x: str) -> float:
  v = float(x)
  return v / 100.0 if v > 1.0 else v


def read_zebra_init(path: str) -> List[Tuple[int, str, str, str, str]]:
  rows: List[Tuple[int, str, str, str, str]] = []
  with open(path, "r", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for r in reader:
      house_id = int(r["H"])
      agent_id = r["I"]
      drink = r["D"]
      smokes = r["S"]
      pet = r["P"]
      rows.append((house_id, agent_id, drink, smokes, pet))
  rows.sort(key=lambda x: x[0])
  return rows


def read_strategies(path: str) -> Dict[str, Strategy]:
  out: Dict[str, Strategy] = {}
  with open(path, "r", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for r in reader:
      agent_id = r["I"]
      out[agent_id] = Strategy(
        p_left=_to_prob(r["PLeft"]),
        p_right=_to_prob(r["PRight"]),
        p_home=_to_prob(r["PHome"]),
        p_house_exch=_to_prob(r["PHouseExch"]),
        p_pet_exch=_to_prob(r["PPetExch"]),
      )
  return out


def neighbor_left(h: int, n_houses: int) -> int:
  return ((h - 2) % n_houses) + 1


def neighbor_right(h: int, n_houses: int) -> int:
  return (h % n_houses) + 1


def travel_days_6(from_house: int, to_house: int) -> int:
  right = {1: 2, 2: 1, 3: 2, 4: 2, 5: 2, 6: 3}
  left = {1: 3, 2: 2, 3: 1, 4: 2, 5: 2, 6: 2}
  if to_house == neighbor_right(from_house, 6):
    return right[from_house]
  if to_house == neighbor_left(from_house, 6):
    return left[from_house]
  return 1


def travel_days(from_house: int, to_house: int, n_houses: int) -> int:
  if from_house == to_house:
    return 0
  if n_houses == 6:
    return travel_days_6(from_house, to_house)
  return 1


def sample_direction(s: Strategy, rng: random.Random) -> str:
  x = rng.random()
  if x < s.p_left:
    return "left"
  x -= s.p_left
  if x < s.p_right:
    return "right"
  return "home"


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


def choose_other_value_str(values: List[str], true_v: str, rng: random.Random) -> str:
  if not values:
    return true_v
  if len(values) == 1:
    return values[0]
  cand = true_v
  while cand == true_v:
    cand = rng.choice(values)
  return cand


def choose_other_value_int(n: int, true_v: int, rng: random.Random) -> int:
  if n <= 1:
    return true_v
  cand = true_v
  while cand == true_v:
    cand = rng.randint(1, n)
  return cand


def learn_direct(
  belief: Belief,
  other: Agent,
  n_houses: int,
  domains: Domains,
  noise: float,
  rng: random.Random,
) -> None:
  house_v = other.house_id
  drink_v = other.drink
  smokes_v = other.smokes
  pet_v = other.pet

  if noise > 0.0 and rng.random() < noise:
    house_v = choose_other_value_int(n_houses, house_v, rng)
  if noise > 0.0 and rng.random() < noise:
    drink_v = choose_other_value_str(domains.drinks, drink_v, rng)
  if noise > 0.0 and rng.random() < noise:
    smokes_v = choose_other_value_str(domains.smokes, smokes_v, rng)
  if noise > 0.0 and rng.random() < noise:
    pet_v = choose_other_value_str(domains.pets, pet_v, rng)

  belief.houses[other.idx] = house_v
  belief.drinks[other.idx] = drink_v
  belief.smokes[other.idx] = smokes_v
  belief.pets[other.idx] = pet_v


def merge_beliefs(dst: Belief, src: Belief) -> None:
  dst.houses.update(src.houses)
  dst.drinks.update(src.drinks)
  dst.smokes.update(src.smokes)
  dst.pets.update(src.pets)


def sa_any(b: Belief, n_agents: int) -> float:
  total = 4 * n_agents
  known = len(b.houses) + len(b.drinks) + len(b.smokes) + len(b.pets)
  return known / total if total > 0 else 0.0


def sa_m1_true(b: Belief, agents: List[Agent], n_agents: int) -> float:
  total = 4 * n_agents
  ok = 0

  for j, v in b.houses.items():
    if v == agents[j].house_id:
      ok += 1
  for j, v in b.drinks.items():
    if v == agents[j].drink:
      ok += 1
  for j, v in b.smokes.items():
    if v == agents[j].smokes:
      ok += 1
  for j, v in b.pets.items():
    if v == agents[j].pet:
      ok += 1

  return ok / total if total > 0 else 0.0


def _pad_row(row: List, width: int = 10) -> List:
  if len(row) >= width:
    return row[:width]
  return row + [""] * (width - len(row))


def build_agents(
  n_agents: int,
  houses: int,
  seed: int,
  zebra_init: str,
  zebra_strat: str,
) -> Tuple[List[Agent], Domains, int]:
  rng = random.Random(seed)

  if n_agents == 6 and houses == 6 and Path(zebra_init).exists() and Path(zebra_strat).exists():
    init_rows = read_zebra_init(zebra_init)
    strat = read_strategies(zebra_strat)

    drinks = sorted({r[2] for r in init_rows})
    smokes = sorted({r[3] for r in init_rows})
    pets = sorted({r[4] for r in init_rows})
    domains = Domains(drinks=drinks, smokes=smokes, pets=pets)

    agents: List[Agent] = []
    for idx, (house_id, agent_id, drink, smokes_v, pet) in enumerate(init_rows):
      s = strat.get(agent_id, Strategy(1 / 3, 1 / 3, 1 / 3, 0.0, 0.0))
      agents.append(
        Agent(
          agent_id=agent_id,
          idx=idx,
          house_id=house_id,
          location=house_id,
          drink=drink,
          smokes=smokes_v,
          pet=pet,
          strategy=s,
          trip=Trip(active=False, from_house=house_id, to_house=house_id, days_left=0, start_event_id=0),
        )
      )
    return agents, domains, 6

  base_drinks = [f"d{i}" for i in range(6)]
  base_smokes = [f"s{i}" for i in range(6)]
  base_pets = [f"p{i}" for i in range(6)]
  domains = Domains(drinks=base_drinks, smokes=base_smokes, pets=base_pets)

  agents: List[Agent] = []
  for i in range(n_agents):
    house_id = (i % houses) + 1
    agents.append(
      Agent(
        agent_id=f"a{i}",
        idx=i,
        house_id=house_id,
        location=house_id,
        drink=base_drinks[i % 6],
        smokes=base_smokes[i % 6],
        pet=base_pets[i % 6],
        strategy=Strategy(1 / 3, 1 / 3, 1 / 3, 0.0, 0.0),
        trip=Trip(active=False, from_house=house_id, to_house=house_id, days_left=0, start_event_id=0),
      )
    )
  return agents, domains, houses


def run_sim(
  agents: List[Agent],
  days: int,
  rng: random.Random,
  share_mode: str,
  noise: float,
  n_houses: int,
  domains: Domains,
  log_path: Optional[str],
  sa_path: Optional[str],
  sa_sample: int,
) -> None:
  n_agents = len(agents)
  beliefs = init_beliefs(agents)

  log_rows: List[List] = []
  sa_rows: List[List] = []
  event_id = 0

  for day in range(1, days + 1):
    arrived_today: List[int] = []

    # 1) Finish active trips
    for a in agents:
      if not a.trip.active:
        continue

      a.trip.days_left -= 1
      if a.trip.days_left > 0:
        continue

      dest = a.trip.to_house
      start_id = a.trip.start_event_id

      a.location = dest
      a.trip.active = False

      host_exists = False
      for x in agents:
        if x.trip.active:
          continue
        if (x.house_id == dest) and (x.location == dest):
          host_exists = True
          break

      r = 1 if host_exists else 0

      event_id += 1
      log_rows.append(_pad_row([event_id, day, "FinishTrip", start_id, a.agent_id, r]))

      if r == 0:
        to_home = a.house_id
        d = travel_days(dest, to_home, n_houses)
        event_id += 1
        a.trip = Trip(active=True, from_house=dest, to_house=to_home, days_left=d, start_event_id=event_id)
        log_rows.append(_pad_row([event_id, day, "startTrip", a.agent_id, dest, to_home, d]))
      else:
        arrived_today.append(a.idx)

    # 2) Build hosts map (who is at home now)
    host_by_house: Dict[int, int] = {}
    for x in agents:
      if x.trip.active:
        continue
      if (x.location == x.house_id):
        host_by_house[x.location] = x.idx

    # 3) Interactions only for those who arrived to a house with a host
    for visitor_idx in arrived_today:
      visitor = agents[visitor_idx]
      house = visitor.location

      host_idx = host_by_house.get(house)
      if host_idx is None:
        continue
      if host_idx == visitor_idx:
        continue

      host = agents[host_idx]

      learn_direct(beliefs[visitor_idx], host, n_houses, domains, noise, rng)
      learn_direct(beliefs[host_idx], visitor, n_houses, domains, noise, rng)

      if share_mode == "meet":
        merge_beliefs(beliefs[visitor_idx], beliefs[host_idx])
        merge_beliefs(beliefs[host_idx], beliefs[visitor_idx])

      if rng.random() <= visitor.strategy.p_pet_exch and rng.random() <= host.strategy.p_pet_exch:
        v_before = visitor.pet
        h_before = host.pet
        visitor.pet, host.pet = host.pet, visitor.pet

        beliefs[visitor_idx].pets[visitor_idx] = visitor.pet
        beliefs[host_idx].pets[host_idx] = host.pet

        event_id += 1
        log_rows.append(
          _pad_row([event_id, day, "changePet", visitor.agent_id, host.agent_id, v_before, h_before, visitor.pet, host.pet])
        )

      if rng.random() <= visitor.strategy.p_house_exch and rng.random() <= host.strategy.p_house_exch:
        v_before = visitor.house_id
        h_before = host.house_id
        visitor.house_id, host.house_id = host.house_id, visitor.house_id

        beliefs[visitor_idx].houses[visitor_idx] = visitor.house_id
        beliefs[host_idx].houses[host_idx] = host.house_id

        event_id += 1
        log_rows.append(
          _pad_row([event_id, day, "changeHouse", visitor.agent_id, host.agent_id, v_before, h_before, visitor.house_id, host.house_id])
        )

    # 4) After meeting: visitors go (back) home if needed
    for visitor_idx in arrived_today:
      a = agents[visitor_idx]
      if a.trip.active:
        continue
      if a.location == a.house_id:
        continue
      from_h = a.location
      to_h = a.house_id
      d = travel_days(from_h, to_h, n_houses)
      event_id += 1
      a.trip = Trip(active=True, from_house=from_h, to_house=to_h, days_left=d, start_event_id=event_id)
      log_rows.append(_pad_row([event_id, day, "startTrip", a.agent_id, from_h, to_h, d]))

    # 5) Agents at home start new trips by strategy
    for a in agents:
      if a.trip.active:
        continue
      if a.location != a.house_id:
        continue

      direction = sample_direction(a.strategy, rng)
      if direction == "home":
        continue

      to_h = neighbor_left(a.location, n_houses) if direction == "left" else neighbor_right(a.location, n_houses)
      from_h = a.location
      d = travel_days(from_h, to_h, n_houses)

      event_id += 1
      a.trip = Trip(active=True, from_house=from_h, to_house=to_h, days_left=d, start_event_id=event_id)
      log_rows.append(_pad_row([event_id, day, "startTrip", a.agent_id, from_h, to_h, d]))

    # 6) SA logging
    if sa_path is not None:
      avg_any = sum(sa_any(beliefs[i], n_agents) for i in range(n_agents)) / n_agents

      if sa_sample <= 0 or sa_sample >= n_agents:
        sample_idxs = list(range(n_agents))
      else:
        sample_idxs = rng.sample(range(n_agents), sa_sample)

      avg_m1 = sum(sa_m1_true(beliefs[i], agents, n_agents) for i in sample_idxs) / len(sample_idxs)
      sa_rows.append([day, avg_any, avg_m1])

  if log_path is not None:
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
      w = csv.writer(f, delimiter=";")
      w.writerow(["eventID", "day", "event", "a", "b", "c", "d", "e", "f", "g"])
      w.writerows(log_rows)

  if sa_path is not None:
    p = Path(sa_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
      w = csv.writer(f, delimiter=";")
      w.writerow(["day", "avg_sa_any", "avg_sa_m1"])
      w.writerows(sa_rows)


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--agents", type=int, default=6)
  ap.add_argument("--houses", type=int, default=6)
  ap.add_argument("--days", type=int, default=200)
  ap.add_argument("--seed", type=int, default=1)
  ap.add_argument("--share", choices=["none", "meet"], default="meet")
  ap.add_argument("--noise", type=float, default=0.0)
  ap.add_argument("--log", type=int, default=1)
  ap.add_argument("--sa", type=int, default=1)
  ap.add_argument("--sa_sample", type=int, default=50)
  args = ap.parse_args()

  agents, domains, houses = build_agents(
    n_agents=args.agents,
    houses=args.houses,
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
    noise=args.noise,
    n_houses=houses,
    domains=domains,
    log_path=log_path,
    sa_path=sa_path,
    sa_sample=args.sa_sample,
  )

  print("ok")


if __name__ == "__main__":
  main()
