import argparse
import csv
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt


def read_bench(path: str) -> Tuple[List[int], List[float], List[float]]:
  xs: List[int] = []
  ys: List[float] = []
  es: List[float] = []

  with open(path, "r", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for r in reader:
      xs.append(int(r["n_agents"]))
      ys.append(float(r["t_ms_avg"]))
      es.append(float(r["t_ms_std"]))

  return xs, ys, es


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--inputs", nargs="+", required=True)
  ap.add_argument("--labels", nargs="+", required=True)
  ap.add_argument("--out", type=str, default="data/logs/bench.png")
  args = ap.parse_args()

  if len(args.inputs) != len(args.labels):
    raise SystemExit("inputs and labels must have same length")

  for path, label in zip(args.inputs, args.labels):
    xs, ys, es = read_bench(path)
    plt.errorbar(xs, ys, yerr=es, marker="o", linewidth=1, label=label)

  plt.xlabel("N")
  plt.ylabel("T (ms)")
  plt.grid(True, alpha=0.3)
  plt.legend()

  out = Path(args.out)
  out.parent.mkdir(parents=True, exist_ok=True)
  plt.savefig(out, dpi=200, bbox_inches="tight")
  print(f"saved {out}")


if __name__ == "__main__":
  main()
