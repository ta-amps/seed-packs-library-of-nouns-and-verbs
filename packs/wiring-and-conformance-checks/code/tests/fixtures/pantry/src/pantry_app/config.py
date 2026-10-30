"""Settings, read from and written to a JSON file."""

import json
from dataclasses import asdict, dataclass


@dataclass
class Config:
    slot_minutes: int = 15
    open_hour: int = 9
    reminder_hours: int = 24


def load_config(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return Config(slot_minutes=data.get("slot_minutes", 15), open_hour=data.get("open_hour", 9))


def save_config(config, path):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(asdict(config), handle)
