#!/usr/bin/env python3
import json
import os
import sys


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


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("Antigravity")
        return

    # 1. State & Mode
    state = data.get("agent_state") or "idle"
    mode = data.get("cycle_mode") or "auto"

    # 2. Model & Effort
    model_obj = data.get("model") or {}
    model = model_obj.get("display_name") or model_obj.get("id") or "No Model"
    effort = model_obj.get("effort")
    model_str = f"{model} ({effort})" if effort else model

    # 3. Context Window & Tokens
    cw = data.get("context_window") or {}
    in_tok = cw.get("total_input_tokens") or 0
    out_tok = cw.get("total_output_tokens") or 0
    ctx_max = cw.get("context_window_size") or 0
    ctx_pct = cw.get("used_percentage") or 0.0
    max_part = f" / {fmt_tokens(ctx_max)} max" if ctx_max > 0 else ""
    ctx_str = f"Ctx: {ctx_pct:.1f}% ({fmt_tokens(in_tok)} in / {fmt_tokens(out_tok)} out{max_part})"

    # 4. Quotas
    quota_obj = data.get("quota") or {}
    quota_parts = []
    if isinstance(quota_obj, dict):
        for key, val in quota_obj.items():
            if not isinstance(val, dict) or val.get("disabled"):
                continue
            name = key.replace("gemini-", "")
            rem_frac = val.get("remaining_fraction")
            if rem_frac is not None:
                rem_pct = f"{rem_frac * 100:.1f}%"
            elif val.get("remaining_amount") is not None:
                rem_pct = str(val.get("remaining_amount"))
            else:
                continue
            reset_str = fmt_time(val.get("reset_in_seconds"))
            if reset_str:
                quota_parts.append(f"{name}: {rem_pct} ({reset_str})")
            else:
                quota_parts.append(f"{name}: {rem_pct}")

    # 5. VCS / Git
    vcs = data.get("vcs") or {}
    branch = vcs.get("branch")
    dirty = "*" if vcs.get("dirty") else ""
    git_str = f" | Git: {branch}{dirty}" if branch else ""

    # Assemble output
    parts = [f"[{state}:{mode}] {model_str}", ctx_str]
    if quota_parts:
        parts.append("Quota: " + ", ".join(quota_parts))

    print(" | ".join(parts) + git_str)


if __name__ == "__main__":
    main()
