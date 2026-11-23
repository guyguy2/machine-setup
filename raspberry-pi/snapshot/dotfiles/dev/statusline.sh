#!/usr/bin/env python3
import json
import os
import sys

# 256-color ANSI palette matching a clean, readable dark-terminal status line
RESET = "\033[0m"
GRAY = "\033[38;5;244m"
CYAN = "\033[38;5;38m"
BLUE = "\033[38;5;75m"
GREEN = "\033[38;5;77m"
YELLOW = "\033[38;5;179m"
RED = "\033[38;5;203m"
PURPLE = "\033[38;5;141m"

SEP = f" {GRAY}|{RESET} "


def fmt_tokens(n):
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_time(seconds):
    if not seconds or seconds <= 0:
        return ""
    seconds = int(seconds)
    if seconds >= 86400:
        return f"{seconds // 86400}d{(seconds % 86400) // 3600}h"
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60}m"
    return f"{seconds // 60}m"


def fmt_dir(path):
    if not path:
        return ""
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if home and path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


def usage_color(pct):
    if pct >= 80:
        return RED
    if pct >= 60:
        return YELLOW
    return GREEN


def quota_color(pct_left):
    if pct_left < 20:
        return RED
    if pct_left < 50:
        return YELLOW
    return GREEN


def state_color(state):
    if state == "idle":
        return GREEN
    if state in ("working", "tool_use", "reviewing", "initializing"):
        return YELLOW
    if state == "error":
        return RED
    return GRAY


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print(f"🤖 {CYAN}Antigravity{RESET}")
        return

    # 1. State & Mode
    state = data.get("agent_state") or "idle"
    mode = data.get("cycle_mode") or "auto"
    state_str = f"{GRAY}[{state_color(state)}{state}{GRAY}:{CYAN}{mode}{GRAY}]{RESET}"

    # 2. Model & Effort
    model_obj = data.get("model") or {}
    model = model_obj.get("display_name") or model_obj.get("id") or "No Model"
    effort = model_obj.get("effort")
    model_name = f"{model} ({effort})" if effort else model
    model_str = f"{state_str} 🤖 {CYAN}{model_name}{RESET}"

    # 3. Context Window & Tokens
    cw = data.get("context_window") or {}
    in_tok = cw.get("total_input_tokens") or 0
    out_tok = cw.get("total_output_tokens") or 0
    total_tok = in_tok + out_tok
    ctx_max = cw.get("context_window_size") or 0
    ctx_pct = float(cw.get("used_percentage") or 0.0)
    tok_part = f"{fmt_tokens(total_tok)}/{fmt_tokens(ctx_max)}" if ctx_max > 0 else fmt_tokens(total_tok)
    pct_clr = usage_color(ctx_pct)
    ctx_str = f"📊 {BLUE}{tok_part}{RESET} {pct_clr}(▲ {ctx_pct:.1f}% used){RESET}"

    # 4. Quotas
    quota_obj = data.get("quota") or {}
    active_quotas = []
    if isinstance(quota_obj, dict):
        for key, val in quota_obj.items():
            if not isinstance(val, dict) or val.get("disabled"):
                continue
            name = key.replace("gemini-", "")
            rem_frac = val.get("remaining_fraction")
            rem_amt = val.get("remaining_amount")
            if rem_frac is not None:
                pct_left = float(rem_frac) * 100
                q_clr = quota_color(pct_left)
                val_str = f"{q_clr}▼ {pct_left:.1f}% left{RESET}"
            elif rem_amt is not None:
                val_str = f"{GREEN}{rem_amt} left{RESET}"
            else:
                continue
            reset_str = fmt_time(val.get("reset_in_seconds"))
            reset_part = f" {GRAY}({reset_str}){RESET}" if reset_str else ""
            active_quotas.append((name, f"{val_str}{reset_part}"))

    quota_str = ""
    if active_quotas:
        if len(active_quotas) == 1:
            quota_body = active_quotas[0][1]
        else:
            quota_body = f"{GRAY}, {RESET}".join(
                f"{GRAY}{name}:{RESET} {val}" for name, val in active_quotas
            )
        quota_str = f"⏳ {PURPLE}Quota:{RESET} {quota_body}"

    # 5. Working Directory
    ws = data.get("workspace") or {}
    cwd = ws.get("current_dir") or data.get("cwd") or ""
    dir_display = fmt_dir(cwd)
    dir_str = f"📁 {YELLOW}{dir_display}{RESET}" if dir_display else ""

    # 6. VCS / Git
    vcs = data.get("vcs") or {}
    branch = vcs.get("branch")
    dirty = f"{RED}*{RESET}" if vcs.get("dirty") else ""
    git_str = f"🌿 {GREEN}{branch}{RESET}{dirty}" if branch else ""

    # Assemble output
    parts = [model_str, ctx_str]
    if quota_str:
        parts.append(quota_str)
    if dir_str:
        parts.append(dir_str)
    if git_str:
        parts.append(git_str)

    print(SEP.join(parts))


if __name__ == "__main__":
    main()
