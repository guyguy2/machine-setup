"""A stand-in for the sorter's `mail` command (its "Choices" contract), so tests never touch real mail.

conftest.py wraps this in an executable and points PI_STATUS_MAIL_BIN at it. It appends its argv to
$FAKE_MAIL_DIR/calls.jsonl, then either replays $FAKE_MAIL_DIR/reply.json ({"exit": n, "stdout": "..."}) or acts
like the real command on the state file in $PI_STATUS_MAIL_STATE: decide, undo, trash and the draft commands rewrite it.
A draft "written by Claude" is canned text that echoes the note.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

CHOICES = ("action", "respond", "review", "delete")


def finish(code: int, out: dict) -> NoReturn:
    print(json.dumps(out))
    sys.exit(code)


def recount(state: dict) -> None:
    threads = state["threads"]
    for q in state["queues"]:
        mine = [t for t in threads if t["queue"] == q["id"]]
        q["count"] = len(state["notes"]) if q["id"] == "agent-notes" else len(mine)
        if q["id"] in CHOICES:
            q["confirmed"] = sum(1 for t in mine if t.get("decided"))
        if q["id"] == "waiting":
            q["overdue"] = sum(1 for t in mine if t.get("overdue"))
    state["trash"] = {"marked": [t["id"] for t in threads if (t.get("decided") or {}).get("queue") == "delete"]}


def main(argv: list[str]) -> None:
    folder = Path(os.environ["FAKE_MAIL_DIR"])
    with open(folder / "calls.jsonl", "a") as f:
        f.write(json.dumps(argv) + "\n")
    reply = folder / "reply.json"
    if reply.exists():
        r = json.loads(reply.read_text())
        print(r.get("stdout", ""))
        sys.exit(r.get("exit", 0))
    if argv[-3:] != ["--via", "web", "--json"]:
        finish(3, {"ok": False, "error": "usage"})
    cmd, args = argv[0], argv[1:-3]
    path = Path(os.environ["PI_STATUS_MAIL_STATE"])
    state = json.loads(path.read_text())
    by_id = {t["id"]: t for t in state["threads"]}
    if cmd == "decide":
        thread, queue = args
        t = by_id.get(thread) or finish(5, {"ok": False, "error": f"unknown thread {thread}"})
        if queue in ("done", "nar"):
            state["threads"].remove(t)  # off the page, but still known (a reason can follow), as in the real sorter
            t["decided"] = {"queue": queue, "via": "web"}
            state.setdefault("_hidden", []).append(t)
        else:
            t["decided"] = {"queue": queue, "via": "web", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            t["queue"] = queue
        out = {"ok": True, "thread": thread, "queue": queue}
    elif cmd == "reason":
        thread, text = args
        hidden = {x["id"]: x for x in state.get("_hidden", [])}
        t = by_id.get(thread) or hidden.get(thread) or finish(5, {"ok": False, "error": "unknown thread"})
        if not t.get("decided"):
            finish(5, {"ok": False, "error": "choose first, then add your reason"})
        t["decided"]["reason"] = text or None
        out = {"ok": True, "thread": thread, "reason": text or None}
    elif cmd == "accept":
        n = 0
        for pair in args:
            thread, queue = pair.split(":")
            t = by_id.get(thread)
            if t and not t.get("decided") and (t.get("rec") or {}).get("queue") == queue:
                t["decided"] = {"queue": queue, "via": "web:all", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                t["queue"] = queue
                n += 1
        out = {"ok": True, "accepted": n, "failed": 0, "skipped": len(args) - n}
    elif cmd == "undo":
        t = by_id.get(args[0]) or finish(5, {"ok": False, "error": "unknown thread"})
        if not t.get("decided"):
            finish(5, {"ok": False, "error": "nothing to undo"})
        t["decided"] = None
        t["queue"] = (t.get("rec") or {}).get("queue") or "inbox"
        out = {"ok": True, "thread": t["id"]}
    elif cmd in ("draft", "draft-save", "draft-drop"):
        t = by_id.get(args[0]) or finish(5, {"ok": False, "error": "unknown thread"})
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        d = t.get("draft")
        if cmd == "draft":
            note = args[2] if args[1:2] == ["--note"] else None
            body = f"Hi {t['from_name'].split()[0]},\n\nThanks for your note. [your answer]{' (' + note + ')' if note else ''}\n\nMe"
            t["draft"] = {**(d or {"in_gmail": False, "saved": None}), "body": body, "note": note, "source": "claude",
                          "updated": now, "older": False}
            t["draft"]["unsaved"] = t["draft"]["in_gmail"]
            out = {"ok": True, "thread": t["id"], "body": body}
        elif cmd == "draft-save":
            if (d or {}).get("gmail_edited"):
                finish(5, {"ok": False, "error": "this draft was changed in Gmail since; edit it there (Open in Gmail)"})
            updated = bool(d and d.get("in_gmail"))
            t["draft"] = {**(d or {"note": None}), "body": args[1], "source": "you", "updated": now, "in_gmail": True,
                          "saved": now, "unsaved": False, "older": False}
            out = {"ok": True, "thread": t["id"], "gmail_draft_id": "r1", "updated": updated}
        else:
            if not d:
                finish(5, {"ok": False, "error": "no draft to discard"})
            t["draft"] = None
            out = {"ok": True, "thread": t["id"], "in_gmail": d["in_gmail"]}
    elif cmd == "trash" and args[:1] == ["--yes"]:
        ids = args[1:]
        marked = set(state.get("trash", {}).get("marked", []))
        if not set(ids) <= marked:
            finish(5, {"ok": False, "error": "not marked: " + " ".join(sorted(set(ids) - marked))})
        state["threads"] = [t for t in state["threads"] if t["id"] not in ids]
        out = {"ok": True, "trashed": len(ids)}
    else:
        finish(3, {"ok": False, "error": "usage"})
    recount(state)
    path.write_text(json.dumps(state))
    finish(0, out)


if __name__ == "__main__":
    main(sys.argv[1:])
