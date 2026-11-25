#!/usr/bin/env bash
# Shared runner for momus, ariadne, and grug.
# Lives in the momus skill: atlas sync copies one skill directory, so a
# repo-root script would not travel with the synced commands. Ariadne and
# grug source ../momus/scripts/review-engine.sh, which is the same relative
# path in this repo and under a repo's .agents/skills/.
#
# Picks a capable model on a provider other than the one that called it.
# A provider that is out of usage budget is skipped. The caller's provider
# is last, and then only at that provider's capable model — never a lesser
# model that happened to make the call. There is no Claude default.
#
# Capable models (one home for these ids):
#   grok    grok-4.7       `grok models` default
#   claude  opus           ~/.claude/settings.json model alias
#   codex   gpt-5.6-sol    ~/.codex/config.toml model
#
# REVIEW_DRY=1 prints the caller and the try order and does not run a model.
# CRITIC_ENGINE / ARIADNE_ENGINE forces one provider and skips rotation.

review_capable_model() {
  case "$1" in
    grok) printf '%s\n' grok-4.7 ;;
    claude) printf '%s\n' opus ;;
    codex) printf '%s\n' gpt-5.6-sol ;;
    *) return 1 ;;
  esac
}

# Prints "engine model". Engine may be empty. Model is the caller's own
# model when its process named one, which may be a lesser variant.
review_detect_caller() {
  python3 - "$@" <<'PY'
import os, shlex, subprocess, sys

override = sys.argv[1] if len(sys.argv) > 1 else ""
agents = {
    "grok": "grok",
    "claude": "claude",
    "codex": "codex",
    "cursor-agent": "cursor",
}

def argv_of(pid):
    try:
        out = subprocess.check_output(
            ["ps", "-ww", "-o", "args=", "-p", str(pid)], text=True
        )
    except (subprocess.CalledProcessError, OSError):
        return []
    text = out.strip()
    if not text:
        return []
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()

def ppid_of(pid):
    try:
        out = subprocess.check_output(
            ["ps", "-o", "ppid=", "-p", str(pid)], text=True
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return 1
    return int(out) if out.isdigit() else 1

def model_of(argv):
    for i, arg in enumerate(argv):
        if arg in ("-m", "--model") and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--model="):
            return arg.split("=", 1)[1]
    return ""

env_engine = override
if not env_engine:
    if os.environ.get("GROK_AGENT"):
        env_engine = "grok"
    elif os.environ.get("CURSOR_AGENT") or os.environ.get("CURSOR_INVOKED_AS"):
        env_engine = "cursor"
    elif os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_THREAD_ID"):
        env_engine = "codex"
    elif os.environ.get("CLAUDECODE"):
        env_engine = "claude"

engine = env_engine
model = ""
pid = os.getppid()
for _ in range(25):
    if pid <= 1:
        break
    argv = argv_of(pid)
    base = os.path.basename(argv[0]) if argv else ""
    mapped = agents.get(base, "")
    if mapped and not engine:
        engine = mapped
    if mapped and (not env_engine or mapped == env_engine) and not model:
        found = model_of(argv)
        if found:
            model = found
    pid = ppid_of(pid)

print(f"{engine} {model}".rstrip())
PY
}

# Provider family of a model id, so a cursor call on sonnet still counts as
# claude and is not reviewed by claude first.
review_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

review_family() {
  local id
  id="$(review_lower "$1")"
  case "$id" in
    grok*) printf '%s\n' grok ;;
    claude*|opus*|sonnet*|haiku*|fable*) printf '%s\n' claude ;;
    gpt*|codex*|o3*|o4*) printf '%s\n' codex ;;
    *) printf '%s\n' "" ;;
  esac
}

# Lines of "engine model", caller's provider last.
review_candidates() {
  local caller_engine="$1" caller_model="$2"
  local family
  family="$(review_family "$caller_model")"
  [[ -n "$family" ]] || family="$caller_engine"
  local engine model line
  local caller_line=""
  for engine in grok claude codex; do
    model="$(review_capable_model "$engine")"
    line="$engine $model"
    if [[ "$engine" == "$family" ]]; then
      caller_line="$line"
    else
      printf '%s\n' "$line"
    fi
  done
  [[ -n "$caller_line" ]] && printf '%s\n' "$caller_line"
}

review_is_budget() {
  local text
  text="$(review_lower "$1")"
  case "$text" in
    *"usage limit"*|*"rate limit"*|*"rate_limit"*|*"quota"*|*"insufficient_quota"*|\
    *"credit balance"*|*"out of credits"*|*"out of usage"*|*"hit your limit"*|\
    *"too many requests"*|*"exceeded your"*|*"billing_hard_limit"*|*"spend limit"*)
      return 0
      ;;
  esac
  return 1
}

review_run_one() {
  local engine="$1" model="$2" prompt="$3"
  local err
  err="$(mktemp)"
  local code=0
  case "$engine" in
    claude)
      printf '%s\n' "$MATERIAL" | claude -p --model "$model" --system-prompt "$prompt" --tools "" \
        >"$REVIEW_OUT" 2>"$err" || code=$?
      ;;
    codex)
      printf '%s\n\n---\n\n# Material to review\n\n%s\n' "$prompt" "$MATERIAL" \
        | codex exec -m "$model" --skip-git-repo-check --sandbox read-only - \
          >"$REVIEW_OUT" 2>"$err" || code=$?
      ;;
    grok)
      printf '%s\n' "$MATERIAL" | env \
        -u GROK_SESSION_ID \
        -u GROK_AGENT \
        -u ORCA_AGENT_SESSION_ID \
        -u ORCA_STRUCTURED_SESSION \
        GROK_CLAUDE_AGENTS_ENABLED=false \
        GROK_CLAUDE_RULES_ENABLED=false \
        GROK_CLAUDE_SKILLS_ENABLED=false \
        GROK_CLAUDE_HOOKS_ENABLED=false \
        GROK_CLAUDE_MCPS_ENABLED=false \
        GROK_CURSOR_AGENTS_ENABLED=false \
        GROK_CURSOR_RULES_ENABLED=false \
        GROK_CURSOR_SKILLS_ENABLED=false \
        GROK_CURSOR_HOOKS_ENABLED=false \
        GROK_CURSOR_MCPS_ENABLED=false \
        grok -p -m "$model" \
          --system-prompt-override "$prompt" \
          --tools '' \
          --no-subagents \
          --disable-web-search \
          --no-memory \
          --no-plan \
          --max-turns 3 \
          --permission-mode dontAsk \
          --cwd "$REVIEW_WORKDIR" \
          --verbatim \
          --output-format plain \
          >"$REVIEW_OUT" 2>"$err" || code=$?
      ;;
    *)
      echo "$NAME: no runner for $engine" >&2
      rm -f "$err"
      return 1
      ;;
  esac
  if [[ "$code" -eq 0 && -s "$REVIEW_OUT" ]]; then
    rm -f "$err"
    return 0
  fi
  local detail
  detail="$(cat "$err" 2>/dev/null || true)"
  rm -f "$err"
  if review_is_budget "$detail"; then
    echo "$NAME: $engine $model is out of budget" >&2
    return 2
  fi
  echo "$NAME: $engine $model failed${detail:+: ${detail//$'\n'/ }}" >&2
  return 1
}

# NAME, PROMPT, and MATERIAL are set by the caller.
review_run() {
  local caller caller_engine caller_model
  local override="${REVIEW_ENGINE_OVERRIDE:-}"
  caller="$(review_detect_caller)"
  caller_engine="${caller%% *}"
  caller_model=""
  [[ "$caller" == *" "* ]] && caller_model="${caller#* }"

  local -a candidates=()
  local line
  if [[ -n "$override" ]]; then
    local forced
    forced="$(review_capable_model "$override" || true)"
    if [[ -z "$forced" ]]; then
      echo "$NAME: unknown engine '$override' (use grok, claude, or codex)." >&2
      return 2
    fi
    candidates=("$override $forced")
  else
    while IFS= read -r line; do
      [[ -n "$line" ]] && candidates+=("$line")
    done < <(review_candidates "$caller_engine" "$caller_model")
  fi

  if [[ "${REVIEW_DRY:-}" == "1" ]]; then
    echo "$NAME: caller ${caller_engine:-unknown}${caller_model:+ $caller_model}"
    printf '%s\n' "${candidates[@]}" | sed 's/^/try /'
    return 0
  fi

  REVIEW_WORKDIR="$(mktemp -d)"
  REVIEW_OUT="$(mktemp)"
  # shellcheck disable=SC2064
  trap "rm -rf \"$REVIEW_WORKDIR\" \"$REVIEW_OUT\"" RETURN
  cd "$REVIEW_WORKDIR"

  local engine model tried=0
  for line in "${candidates[@]}"; do
    engine="${line%% *}"
    model="${line#* }"
    command -v "$engine" >/dev/null 2>&1 || {
      echo "$NAME: $engine not on PATH, skipping" >&2
      continue
    }
    tried=1
    echo "$NAME: trying $engine $model" >&2
    if review_run_one "$engine" "$model" "$PROMPT"; then
      if [[ -n "$caller_engine" && "$engine" == "$caller_engine" && -z "$override" ]]; then
        echo "$NAME: reviewed by the caller's provider ($engine $model); other providers were unavailable or out of budget" >&2
      else
        echo "$NAME: reviewed by $engine $model" >&2
      fi
      cat "$REVIEW_OUT"
      return 0
    fi
  done
  if [[ "$tried" -eq 0 ]]; then
    echo "$NAME: no review provider on PATH." >&2
  else
    echo "$NAME: every capable provider failed." >&2
  fi
  return 1
}
