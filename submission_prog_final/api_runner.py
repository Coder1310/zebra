import argparse
import requests


def main() -> None:
  ap = argparse.ArgumentParser()
  ap.add_argument("--api", default="http://127.0.0.1:8000")
  ap.add_argument("--agents", type=int, default=100)
  ap.add_argument("--houses", type=int, default=6)
  ap.add_argument("--days", type=int, default=200)
  ap.add_argument("--share", choices=["none", "meet"], default="meet")
  ap.add_argument("--noise", type=float, default=0.0)
  ap.add_argument("--seed", type=int, default=1)
  args = ap.parse_args()

  r = requests.post(f"{args.api}/session/create", json={
    "agents": args.agents,
    "houses": args.houses,
    "days": args.days,
    "share": args.share,
    "noise": args.noise,
    "seed": args.seed,
    "time_delay_sec": 0,
  }, timeout=30)
  r.raise_for_status()
  sid = r.json()["session_id"]

  requests.post(f"{args.api}/session/{sid}/start", timeout=30).raise_for_status()
  requests.post(f"{args.api}/session/{sid}/run", timeout=300).raise_for_status()

  csv_path = requests.get(f"{args.api}/session/{sid}/log/csv", timeout=30).json()["path"]
  xml_path = requests.get(f"{args.api}/session/{sid}/log/xml", timeout=30).json()["path"]
  m_path = requests.get(f"{args.api}/session/{sid}/metrics", timeout=30).json()["path"]

  print(f"session={sid}")
  print(f"csv={csv_path}")
  print(f"xml={xml_path}")
  print(f"metrics={m_path}")


if __name__ == "__main__":
  main()
