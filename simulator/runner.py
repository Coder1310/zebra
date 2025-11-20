import requests
from typing import Dict

from strategy.types import PlayerState, BeliefState, Action
from strategy.base_strategy import decide_action


BASE_URL = "http://127.0.0.1:8000"


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
  resp = requests.post(f"{BASE_URL}/action", json=body)
  resp.raise_for_status()


def main() -> None:
  player_id = "german"
  belief = BeliefState()

  for step in range(5):
    day = send_tick()
    print(f"=== day {day} ===")

    state = get_state(player_id)
    action, belief = decide_action(state, belief)
    send_action(action)

    print(f"player={player_id}, action={action.type}")

  print("simulation finished")


if __name__ == "__main__":
  main()
