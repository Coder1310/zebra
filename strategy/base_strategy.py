import random
from typing import Tuple

from .types import PlayerState, BeliefState, Action


def update_belief_from_state(
  player_state: PlayerState,
  belief_state: BeliefState,
) -> BeliefState:
  """
  Обновляем знания игрока:
  - про себя: дом, питомец, напиток, сигареты;
  - про видимых игроков: их текущий дом (location).
  """
  b = BeliefState(
    houses = dict(belief_state.houses),
    pets = dict(belief_state.pets),
    drinks = dict(belief_state.drinks),
    smokes = dict(belief_state.smokes),
  )

  pid = player_state.player_id
  you = player_state.you

  # свои атрибуты
  b.houses[pid] = int(you["house_id"])
  b.pets[pid] = you["pet"]
  b.drinks[pid] = you["drink"]
  b.smokes[pid] = you["smokes"]

  # видимых игроков — хотя бы дом, где их видим
  for vp in player_state.visible_players:
    b.houses[vp.player_id] = vp.house_id

  return b


def decide_action(
  player_state: PlayerState,
  belief_state: BeliefState,
) -> Tuple[Action, BeliefState]:
  """
  Простая стратегия:
  1) сначала обновляем знания по текущему наблюдению;
  2) потом случайно выбираем направление движения.
  """
  new_belief = update_belief_from_state(player_state, belief_state)

  direction = random.choice(["left", "right", "home"])

  action = Action(
    player_id = player_state.player_id,
    day = player_state.day,
    type = "move",
    direction = direction,
  )

  return action, new_belief
