import argparse
import csv
import time
from pathlib import Path
from typing import List

import random

from simulator.batch_sim import build_agents, run_sim


def mean(xs: List[float]) -> float:
  return sum(xs) / len(xs) if xs else 0.0


def std(xs: List[float]) -> float:
  if len(xs) < 2:
    return 0.0
  m = mean(xs)
  var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
  return var ** 0.5


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--max_agents", type=int, default=1000)
  ap.add_argument("--step", type=int, default=50)
  ap.add_argument("--days", type=int, default=200)
  ap.add_argument("--runs", type=int, default=5)
  ap.add_argument("--seed", type=int, default=1)
  ap.add_argument("--share", choices=["none", "meet"], default="none")
  ap.add_argument("--out", type=str, default="data/logs/bench.csv")
  args = ap.parse_args()

  rows = []

  for n in range(args.step, args.max_agents + 1, args.step):
    times_ms: List[float] = []

    for r in range(args.runs):
      agents = build_agents(
        n_agents=n,
        seed=args.seed + r,
        zebra_init="data/zebra-01.csv",
        zebra_strat="data/ZEBRA-strategies.csv",
      )

      rng = random.Random(args.seed + r)

      t0 = time.perf_counter()
      run_sim(
        agents=agents,
        days=args.days,
        rng=rng,
        share_mode=args.share,
        log_path=None,
        sa_path=None,
      )
      t1 = time.perf_counter()

      times_ms.append((t1 - t0) * 1000.0)

    avg_ms = mean(times_ms)
    std_ms = std(times_ms)

    rows.append([n, avg_ms, std_ms])
    print(f"n={n} avg_ms={avg_ms:.1f} std_ms={std_ms:.1f}")

  out = Path(args.out)
  out.parent.mkdir(parents=True, exist_ok=True)

  with out.open("w", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["n_agents", "t_ms_avg", "t_ms_std"])
    w.writerows(rows)

  print(f"saved {out}")


if __name__ == "__main__":
  main()
