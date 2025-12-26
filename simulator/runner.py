import requests
import csv
from pathlib import Path
from typing import Dict, List, Any

from strategy.types import PlayerState, BeliefState, Action
from strategy.base_strategy import decide_action
from strategy.metrics import calc_sa


BASE_URL = "http://127.0.0.1:8000"

def get_log() -> List[Dict[str, Any]]:
  resp = requests.get(f"{BASE_URL}/log")
  resp.raise_for_status()
  data: List[Dict[str, Any]] = resp.json()
  return data

def save_log_csv(events: List[Dict[str, Any]], filename: str = "data/logs/run1.csv") -> None:
  path = Path(filename)
  path.parent.mkdir(parents = True, exist_ok = True)

  fieldnames = ["event_id", "day", "type", "who", "from_house", "to_house", "success"]

  with path.open("w", newline = "") as f:
    writer = csv.DictWriter(f, fieldnames = fieldnames)
    writer.writeheader()
    for e in events:
      row = {name: e.get(name) for name in fieldnames}
      writer.writerow(row)

  print(f"log saved to {path}")


def send_tick() -> int:
  resp = requests.post(f"{BASE_URL}/tick")
  resp.raise_for_status()
  data: Dict[str, int] = resp.json()
  return data["day"]


def get_state(player_id: str) -> PlayerState:
  resp = requests.get(f"{BASE_URL}/state/{player_id}")
  resp.raise_for_status()
  data = resp.json()
  state = PlayerState.model_validate(data)
  return state


def action_to_request(action: Action) -> Dict:
  payload: Dict = {}

  if action.direction is not None:
    payload["direction"] = action.direction

  if action.accept_house_swap is not None:
    payload["accept_house_swap"] = action.accept_house_swap

  if action.accept_pet_swap is not None:
    payload["accept_pet_swap"] = action.accept_pet_swap

  body: Dict = {
    "player_id": action.player_id,
    "day": action.day,
    "type": action.type,
    "payload": payload or None,
  }

  return body


def send_action(action: Action) -> None:
  body = action_to_request(action)
  resp = requests.post(f"{BASE_URL}/action", json = body)
  resp.raise_for_status()


def main() -> None:
  player_id = "german"
  belief = BeliefState()

  for step in range(5):
    day = send_tick()
    print(f"=== day {day} ===")

    # состояние ДО действия
    state_before = get_state(player_id)
    loc_before = state_before.you.get("location")
    print(f"before: location = {loc_before}")

    action, belief = decide_action(state_before, belief)
    sa_value = calc_sa(belief)

    send_action(action)
    print(f"action: {action.type}, direction = {action.direction}")
    print(f"SA: {sa_value:.2f}")

    # состояние ПОСЛЕ действия
    state_after = get_state(player_id)
    loc_after = state_after.you.get("location")
    print(f"after: location = {loc_after}")
    print()

  print("simulation finished")

  events = get_log()
  save_log_csv(events)


if __name__ == "__main__":
  main()
