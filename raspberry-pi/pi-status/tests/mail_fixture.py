"""A FAKE state.json for the Emails tab (invented senders on .example domains, never real mail).

The file's times are fixed; fresh() moves them all by the same amount so the file looks just written, which is what
the tests and screenshots.py want (otherwise every view would say the sorter is stale).
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "mail-state.json"


def fresh(age: timedelta = timedelta(minutes=4), **change) -> dict:
    """The fixture as if written `age` ago, with top-level keys replaced by `change`."""
    data = json.loads(FIXTURE.read_text())
    shift = datetime.now(timezone.utc) - age - datetime.fromisoformat(data["generated"])

    def move(value: str) -> str:
        return (datetime.fromisoformat(value) + shift).isoformat(timespec="seconds")

    data["generated"] = move(data["generated"])
    data["sync"]["last_success"] = move(data["sync"]["last_success"])
    for item in data["threads"] + data["notes"]:
        item["date"] = move(item["date"])
    for thread in data["threads"]:
        if thread.get("decided"):
            thread["decided"]["at"] = move(thread["decided"]["at"])
    return {**data, **change}


def write_fresh(path: Path, **kwargs) -> Path:
    path.write_text(json.dumps(fresh(**kwargs), indent=2))
    return path
