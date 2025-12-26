import argparse
import csv
import math
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt


def read_sa(path: str) -> Dict[int, float]:
  out: Dict[int, float] = {}
  with open(path, "r", newline = "") as f:
    reader = csv.DictReader(f, delimiter = ";")
    for r in reader:
      out[int(r["day"])] = float(r["avg_sa"])
  return out


def mean(xs: List[float]) -> float:
  return sum(xs) / len(xs) if xs else 0.0


def std(xs: List[float]) -> float:
  if len(xs) < 2:
    return 0.0
  m = mean(xs)
  return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--inputs", nargs = "+", required = True)
  ap.add_argument("--label", required = True)
  ap.add_argument("--out", required = True)
  args = ap.parse_args()

  runs = [read_sa(p) for p in args.inputs]
  days = sorted(runs[0].keys())

  y_mean: List[float] = []
  y_std: List[float] = []

  for d in days:
    vals = [r[d] for r in runs]
    y_mean.append(mean(vals))
    y_std.append(std(vals))

  plt.errorbar(days, y_mean, yerr = y_std, marker = "o", linewidth = 1, label = args.label)
  plt.xlabel("day")
  plt.ylabel("avg SA")
  plt.grid(True, alpha = 0.3)
  plt.legend()
  plt.savefig(args.out, dpi = 200, bbox_inches = "tight")
  print(f"saved {args.out}")


if __name__ == "__main__":
  main()
