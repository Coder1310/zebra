#!/usr/bin/env bash
set -euo pipefail

python -m analysis.bench --max_agents 1000 --step 50 --days 200 --runs 5 --houses 6 --share none --out data/logs/bench_none.csv
python -m analysis.bench --max_agents 1000 --step 50 --days 200 --runs 5 --houses 6 --share meet --out data/logs/bench_meet.csv

python -m analysis.plot_bench \
  --inputs data/logs/bench_none.csv data/logs/bench_meet.csv \
  --labels none meet \
  --out data/logs/bench.png

for s in 1 2 3 4 5; do
  python -m simulator.batch_sim --agents 1000 --houses 6 --days 200 --seed $s --share none --noise 0.0 --log 0 --sa 1
  mv data/logs/batch_sa.csv data/logs/sa_none_seed${s}.csv
done

for s in 1 2 3 4 5; do
  python -m simulator.batch_sim --agents 1000 --houses 6 --days 200 --seed $s --share meet --noise 0.0 --log 0 --sa 1
  mv data/logs/batch_sa.csv data/logs/sa_meet_seed${s}.csv
done

python -m analysis.plot_sa_compare \
  --none "data/logs/sa_none_seed*.csv" \
  --meet "data/logs/sa_meet_seed*.csv" \
  --metric m1 \
  --out data/logs/sa_compare_m1.png

for s in 1 2 3 4 5; do
  python -m simulator.batch_sim --agents 1000 --houses 6 --days 200 --seed $s --share meet --noise 0.2 --log 0 --sa 1
  mv data/logs/batch_sa.csv data/logs/sa_meet_noise02_seed${s}.csv
done

python -m analysis.plot_sa_3curves \
  --none "data/logs/sa_none_seed*.csv" \
  --meet "data/logs/sa_meet_seed*.csv" \
  --noise "data/logs/sa_meet_noise02_seed*.csv" \
  --metric m1 \
  --out data/logs/sa_m1_3curves.png

python -m simulator.batch_sim --agents 6 --houses 6 --days 50 --seed 1 --share meet --noise 0.0 --log 1 --sa 1 --sa_sample 0

echo "done: data/logs/bench.png data/logs/sa_compare_m1.png data/logs/sa_m1_3curves.png data/logs/batch_log.csv"
