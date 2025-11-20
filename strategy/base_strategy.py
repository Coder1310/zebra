import random
from typing import Tuple

from .types import PlayerState, BeliefState, Action


def decide_action(
  player_state: PlayerState,
  belief_state: BeliefState,
) -> Tuple[Action, BeliefState]:
  """
  Простая стратегия: каждый ход случайно выбираем
  left / right / home.
  """
  direction = random.choice(["left", "right", "home"])

  action = Action(
    player_id=player_state.player_id,
    day=player_state.day,
    type="move",
    direction=direction,
  )

  new_belief = belief_state

  return action, new_belief
