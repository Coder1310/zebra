from .types import BeliefState

N_PLAYERS = 2


def calc_sa(belief: BeliefState) -> float:
  """
  Простая метрика SA:
  G = число известных фактов / общее число фактов.

  Факты: дом, питомец, напиток, сигареты для каждого игрока.
  Итого 4 * N_PLAYERS факта.
  """
  total_facts = 4 * N_PLAYERS
  if total_facts == 0:
    return 0.0

  known_facts = (
    len(belief.houses)
    + len(belief.pets)
    + len(belief.drinks)
    + len(belief.smokes)
  )

  return known_facts / total_facts
