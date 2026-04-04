#!/usr/bin/env python3
"""
HyperReal statusline — ANSI color + Unicode symbols (no emoji).
Forces UTF-8 stdout to fix Windows cp1252 encoding crashes.
"""
import sys
import io

# Force UTF-8 stdout FIRST — must happen before any print()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

LOG = Path.home() / ".claude" / "statusline-debug.log"
STATE_DIR = Path.home() / ".claude" / "statusline-state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ── ANSI ────────────────────────────────────────────────────────────
R      = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
UL     = "\033[4m"     # underline
REV    = "\033[7m"     # reverse video
GREEN  = "\033[32m";  BGREEN   = "\033[92m"
YELLOW = "\033[33m";  BYELLOW  = "\033[93m"
RED    = "\033[31m";  BRED     = "\033[91m"
CYAN   = "\033[36m";  BCYAN    = "\033[96m"
WHITE  = "\033[37m"
GRAY   = "\033[90m"
MAGENTA = "\033[35m"; BMAGENTA = "\033[95m"
# Background colors
BG_BLACK  = "\033[40m"
BG_RED    = "\033[41m"
BG_GREEN  = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE   = "\033[44m"
BG_CYAN   = "\033[46m"

# ── Unicode symbols (BMP-only, safe on Windows terminals) ───────────
SYM_SEP      = "·"     # separator
SYM_BRANCH   = "⎇"    # git branch
SYM_DIRTY    = "✦"    # uncommitted changes
SYM_CLEAN    = "✔"    # clean
SYM_CTX_OK   = "●"    # context healthy
SYM_CTX_WARN = "◕"    # context warning
SYM_CTX_HOT  = "◉"    # context critical
SYM_CTX_DEAD = "⊗"    # context toast
SYM_BURN     = "▲"    # burn rate
SYM_TIME     = "◷"    # clock
SYM_COST     = "◈"    # cost
SYM_TURN     = "↺"    # turn counter
SYM_RATE     = "▸"    # rate limit
SYM_FOLDER   = "◧"    # working dir
SYM_MODEL    = "◆"    # model
SYM_DIFF_ADD = "+"
SYM_DIFF_DEL = "−"    # proper minus, not hyphen


def log(msg):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def s_int(v, default=0):
    try:
        return int(float(v)) if v is not None else default
    except Exception:
        return default


def s_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def fmt_duration(ms):
    secs = max(0, s_int(ms) // 1000)
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    if h:  return f"{h}h{m:02d}m"
    if m:  return f"{m}m{s:02d}s"
    return f"{s}s"


def fmt_k(n):
    n = float(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}k"
    return f"{n:.0f}"


def ctx_color(pct):
    if pct < 40:  return BGREEN
    if pct < 70:  return BYELLOW
    return BRED


def ctx_sym(pct):
    if pct < 40:  return SYM_CTX_OK
    if pct < 70:  return SYM_CTX_WARN
    if pct < 90:  return SYM_CTX_HOT
    return SYM_CTX_DEAD


def bar(pct, width=16):
    """Smooth gradient progress bar using partial-fill block chars."""
    pct = max(0, min(100, s_int(pct)))
    total_eighths = round((pct / 100.0) * width * 8)
    full_blocks = total_eighths // 8
    partial = total_eighths % 8
    partial_chars = " ▏▎▍▌▋▊▉"
    color = ctx_color(pct)
    result = color + "█" * full_blocks
    if partial and full_blocks < width:
        result += partial_chars[partial]
        empty = width - full_blocks - 1
    else:
        empty = width - full_blocks
    result += GRAY + "░" * empty + R
    return result


def safe_local_time(epoch_seconds):
    try:
        return datetime.fromtimestamp(int(epoch_seconds)).strftime("%I:%M%p").lstrip("0").lower()
    except Exception:
        return "?"


def load_state(session_id):
    path = STATE_DIR / f"{session_id}.json"
    if not path.exists():
        return {"turns": 0, "last_in": 0, "last_out": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"turns": 0, "last_in": 0, "last_out": 0}


def save_state(session_id, state):
    try:
        (STATE_DIR / f"{session_id}.json").write_text(json.dumps(state), encoding="utf-8")
    except Exception as e:
        log(f"save_state error: {repr(e)}")


def git_info(cwd):
    try:
        chk = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=0.5
        )
        if chk.returncode != 0:
            return None, None
        br = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=0.5
        )
        st = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, text=True, timeout=0.7
        )
        branch = br.stdout.strip() if br.returncode == 0 else "?"
        dirty = bool(st.stdout.strip()) if st.returncode == 0 else False
        return branch, dirty
    except Exception as e:
        log(f"git_info error: {repr(e)}")
        return None, None


def c(text, *codes):
    """Wrap text in ANSI codes."""
    return "".join(codes) + text + R


def sep():
    return f"  {GRAY}{SYM_SEP}{R}  "


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        print(f"statusline error: {e}")
        log(f"json error: {repr(e)}")
        return

    try:
        # ── Extract ─────────────────────────────────────────────────
        model_name = (data.get("model") or {}).get("display_name", "Claude")
        workspace  = data.get("workspace") or {}
        cwd        = workspace.get("current_dir") or os.getcwd()
        folder     = os.path.basename(cwd.rstrip("/\\")) or cwd

        cost_data    = data.get("cost") or {}
        runtime      = fmt_duration(cost_data.get("total_duration_ms", 0))
        total_cost   = s_float(cost_data.get("total_cost_usd"))
        lines_added  = s_int(cost_data.get("total_lines_added"))
        lines_removed = s_int(cost_data.get("total_lines_removed"))

        ctx       = data.get("context_window") or {}
        used_pct  = s_int(ctx.get("used_percentage"), 0)
        ctx_size  = s_int(ctx.get("context_window_size"), 200000)
        total_in  = s_int(ctx.get("total_input_tokens"), 0)
        total_out = s_int(ctx.get("total_output_tokens"), 0)

        current      = ctx.get("current_usage") or {}
        cur_in       = s_int(current.get("input_tokens"), 0)
        cur_out      = s_int(current.get("output_tokens"), 0)
        cache_create = s_int(current.get("cache_creation_input_tokens"), 0)
        cache_read   = s_int(current.get("cache_read_input_tokens"), 0)

        session_id = data.get("session_id", "default")
        state      = load_state(session_id)

        if total_in != state.get("last_in", 0) or total_out != state.get("last_out", 0):
            state["turns"] = state.get("turns", 0) + 1
            state["last_in"] = total_in
            state["last_out"] = total_out

        turns = max(1, state.get("turns", 1))
        save_state(session_id, state)

        burn         = cur_in + 1.3 * cur_out + 0.15 * cache_create + 0.05 * cache_read
        burn_per_msg = burn / turns

        rl    = data.get("rate_limits") or {}
        five  = rl.get("five_hour") or {}
        seven = rl.get("seven_day") or {}

        branch, dirty = git_info(cwd)

        # ── LINE 1: Identity ─────────────────────────────────────────
        #  ◆ Sonnet 4.6  ·  ◧ 3d-render-pipeline  ·  ⎇ feature/cold-start ✦  ·  ◷ 4m12s ↺8
        parts1 = []

        # Reverse-video "chip" for model name
        parts1.append(f"{BOLD}{BG_CYAN}\033[30m {SYM_MODEL} {model_name} {R}")
        parts1.append(c(f"{SYM_FOLDER} {folder}", DIM, WHITE))

        if branch:
            if dirty:
                parts1.append(c(f"{SYM_BRANCH} {branch} ", BYELLOW) + c(SYM_DIRTY, BRED))
            else:
                parts1.append(c(f"{SYM_BRANCH} {branch} {SYM_CLEAN}", BGREEN))
        else:
            parts1.append(c("no git", DIM, GRAY))

        parts1.append(
            c(f"{SYM_TIME} {runtime}", WHITE) +
            c(f"  {SYM_TURN}{turns}", DIM, GRAY)
        )

        diff_str = ""
        if lines_added:   diff_str += c(f" {SYM_DIFF_ADD}{lines_added}", BGREEN)
        if lines_removed: diff_str += c(f" {SYM_DIFF_DEL}{lines_removed}", BRED)
        if diff_str:      parts1.append(diff_str.strip())

        if total_cost > 0:
            parts1.append(c(f"{SYM_COST} ${total_cost:.2f}", BYELLOW))

        line1 = sep().join(parts1)

        # ── LINE 2: Context + Burn + Rate limits ─────────────────────
        #  ● 23%  [████░░░░░░░░░░░░]  142k/1.0M  ·  ▲ 3.2k/msg  ·  ▸ 5h 12%  7d 3%
        pct_color = ctx_color(used_pct)
        tokens_used = fmt_k(cur_in + cache_create + cache_read)

        # Background-highlighted context % chip
        bg_ctx = BG_GREEN if used_pct < 40 else BG_YELLOW if used_pct < 70 else BG_RED
        ctx_chip = f"{BOLD}{bg_ctx}\033[30m {ctx_sym(used_pct)} {used_pct}% {R}"

        # Cache efficiency
        total_input_tokens = cur_in + cache_create + cache_read
        cache_hit_pct = round((cache_read / total_input_tokens) * 100) if total_input_tokens > 0 else 0
        cache_str = c(f"⟳{cache_hit_pct}%", BMAGENTA) if cache_hit_pct > 0 else ""

        ctx_badge = (
            ctx_chip +
            f"  [{bar(used_pct)}]" +
            c(f"  {tokens_used}/{fmt_k(ctx_size)}", DIM, GRAY) +
            (f"  {cache_str}" if cache_str else "")
        )

        burn_color = BRED if burn_per_msg > 15000 else BYELLOW if burn_per_msg > 5000 else BGREEN
        burn_badge = c(f"{SYM_BURN} {burn_per_msg/1000:.1f}k/msg", burn_color)

        rl_parts = []
        if five.get("used_percentage") is not None:
            pct5 = round(s_float(five["used_percentage"]))
            c5   = BGREEN if pct5 < 50 else BYELLOW if pct5 < 80 else BRED
            seg  = c(f"5h {pct5}%", c5)
            if five.get("resets_at"):
                seg += c(f" →{safe_local_time(five['resets_at'])}", DIM, GRAY)
            rl_parts.append(seg)

        if seven.get("used_percentage") is not None:
            pct7 = round(s_float(seven["used_percentage"]))
            c7   = BGREEN if pct7 < 50 else BYELLOW if pct7 < 80 else BRED
            seg  = c(f"7d {pct7}%", c7)
            if seven.get("resets_at"):
                seg += c(f" →{safe_local_time(seven['resets_at'])}", DIM, GRAY)
            rl_parts.append(seg)

        parts2 = [ctx_badge, burn_badge]
        if rl_parts:
            parts2.append(c(f"{SYM_RATE} ", GRAY) + "  ".join(rl_parts))

        line2 = sep().join(parts2)

        print(line1)
        print(line2)
        log("render ok")

    except Exception as e:
        print(f"statusline error: {e}")
        log(f"runtime error: {repr(e)}")


if __name__ == "__main__":
    main()
