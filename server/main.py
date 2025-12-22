from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Literal, Optional, Dict

app = FastAPI()


class VisiblePlayer(BaseModel):
  player_id: str
  house_id: int
  is_at_home: bool


class Event(BaseModel):
  event_id: int
  day: int
  type: str
  who: Optional[str] = None
  from_house: Optional[int] = None
  to_house: Optional[int] = None
  who1: Optional[str] = None
  who2: Optional[str] = None
  success: Optional[bool] = None


class StateResponse(BaseModel):
  day: int
  player_id: str
  you: Dict[str, str]
  neighbors: Dict[str, int]
  visible_players: List[VisiblePlayer]
  events_since_last_turn: List[Event]


class ActionPayload(BaseModel):
  direction: Optional[Literal["left", "right", "home"]] = None
  accept_house_swap: Optional[bool] = None
  accept_pet_swap: Optional[bool] = None


class ActionRequest(BaseModel):
  player_id: str
  day: int
  type: Literal["move", "stay", "trade_response"]
  payload: Optional[ActionPayload] = None


WORLD_STATE: Dict[str, dict] = {}
CURRENT_DAY: int = 0
EVENT_LOG: List[Event] = []


def init_world() -> None:
  global WORLD_STATE, CURRENT_DAY, EVENT_LOG
  CURRENT_DAY = 0
  EVENT_LOG = []
  WORLD_STATE = {
    "english": {
      "house_id": 1,
      "location": 1,
      "nationality": "english",
      "drink": "tea",
      "smokes": "pall_mall",
      "pet": "bird",
    },
    "german": {
      "house_id": 2,
      "location": 2,
      "nationality": "german",
      "drink": "coffee",
      "smokes": "prince",
      "pet": "fish",
    },
  }


@app.on_event("startup")
def on_startup() -> None:
  init_world()


@app.get("/state/{player_id}", response_model=StateResponse)
def get_state(player_id: str) -> StateResponse:
  if player_id not in WORLD_STATE:
    raise HTTPException(status_code=404, detail="unknown player")

  player = WORLD_STATE[player_id]
  day = CURRENT_DAY

  location = player["location"]
  left_house_id = ((location - 2) % 6) + 1
  right_house_id = (location % 6) + 1

  visible_players: List[VisiblePlayer] = []
  for pid, info in WORLD_STATE.items():
    if pid == player_id:
      continue
    visible_players.append(
      VisiblePlayer(
        player_id = pid,
        house_id = info["location"],
        is_at_home = (info["location"] == info["house_id"]),
      )
    )

  day_events = [e for e in EVENT_LOG if e.day == day]

  return StateResponse(
    day = day,
    player_id = player_id,
    you = {
      "house_id": str(player["house_id"]),
      "location": str(player["location"]),
      "nationality": player["nationality"],
      "drink": player["drink"],
      "smokes": player["smokes"],
      "pet": player["pet"],
    },
    neighbors={
      "left_house_id": left_house_id,
      "right_house_id": right_house_id,
    },
    visible_players=visible_players,
    events_since_last_turn=day_events,
  )


@app.post("/action")
def post_action(action: ActionRequest) -> dict:
  if action.player_id not in WORLD_STATE:
    raise HTTPException(status_code=404, detail = "unknown player")

  player = WORLD_STATE[action.player_id]

  if action.type == "move":
    if action.payload is None or action.payload.direction is None:
      raise HTTPException(status_code = 400, detail = "missing direction")

    old_loc = player["location"]

    if action.payload.direction == "left":
      new_loc = ((old_loc - 2) % 6) + 1
    elif action.payload.direction == "right":
      new_loc = (old_loc % 6) + 1
    elif action.payload.direction == "home":
      new_loc = player["house_id"]
    else:
      raise HTTPException(status_code = 400, detail = "bad direction")

    player["location"] = new_loc

    event = Event(
      event_id = len(EVENT_LOG) + 1,
      day = action.day,
      type = "visit",
      who = action.player_id,
      from_house = old_loc,
      to_house = new_loc,
      success = True,
    )
    EVENT_LOG.append(event)

  return {"status": "ok"}

@app.get("/log", response_model = List[Event])
def get_log() -> List[Event]:
  return EVENT_LOG

@app.post("/tick")
def tick() -> dict:
  global CURRENT_DAY
  CURRENT_DAY += 1
  return {"day": CURRENT_DAY}
