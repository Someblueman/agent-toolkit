#!/usr/bin/env bash
# Stable CLI entrypoint: Codex materialization uses Python; OMP and Claude Code keep links.
set -euo pipefail
IFS=$'\n\t'
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  echo "Usage: $0 <codex|omp|claude> [--force] [--dry-run] [--prune] [--check]"
  echo "Codex: --check verifies content; --prune removes retired managed items only."
  echo "OMP: supports --force and --dry-run. Requires existing config drift review."
  echo "Claude: --check verifies links; --prune removes links to deselected toolkit skills."
}

[[ $# -gt 0 ]] || { usage; exit 2; }
if [[ "$1" == "--help" || "$1" == "-h" ]]; then usage; exit 0; fi
AGENT="$1"
shift
if [[ "$AGENT" == "codex" ]]; then
  exec python3 "$REPO_ROOT/scripts/install_codex.py" "$@"
fi
[[ "$AGENT" == "omp" || "$AGENT" == "claude" ]] || { usage; exit 2; }
FORCE=0
DRY_RUN=0
CHECK=0
PRUNE=0
CONFLICTS=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --check) CHECK=1 ;;
    --prune) PRUNE=1 ;;
    --help|-h) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
if [[ "$AGENT" == "omp" && ( $CHECK -eq 1 || $PRUNE -eq 1 ) ]]; then
  usage
  exit 2
fi

log() { printf '[install] %s\n' "$*"; }
warn() { printf '[install] WARN: %s\n' "$*" >&2; }
err() { printf '[install] ERROR: %s\n' "$*" >&2; }
run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '  DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

sync_file() {
  local src="$1" dst="$2"
  if [[ -f "$dst" && ! -L "$dst" ]] && cmp -s "$src" "$dst"; then
    log "ok (unchanged): $dst"
    return
  fi
  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ $FORCE -ne 1 ]]; then
      warn "drift at $dst, skipping (use --force to replace)"
      CONFLICTS=1
      return
    fi
    run rm "$dst"
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp "$src" "$dst"
}

# install_omp - wire the toolkit into ~/.omp/agent. skills/ and agents/ are
# symlinked so the repo stays the source of truth for read-only content.
# config.yml is copied, not linked: OMP owns its config at runtime — it
# normalizes and rewrites the file whenever settings persist, and locks it
# with a sibling config.yml.lock next to the resolved path. A symlink would
# route those writes into the repo copy, clobbering it.
install_omp() {
  local agent_dir="${OMP_AGENT_DIR:-$HOME/.omp/agent}"
  log "installing into $agent_dir (repo: $REPO_ROOT)"

  local link_targets=(
    "skills:$REPO_ROOT/skills"
    "agents:$REPO_ROOT/agents"
  )
  for entry in "${link_targets[@]}"; do
    local name="${entry%%:*}"
    local target="${entry#*:}"
    local dst="$agent_dir/$name"

    if [[ -L "$dst" ]]; then
      local cur
      cur=$(readlink "$dst")
      if [[ "$cur" == "$target" ]]; then
        log "ok (linked): $dst -> $target"
      else
        warn "symlink at $dst points to $cur, replacing"
        run ln -sfn "$target" "$dst"
      fi
      continue
    fi

    if [[ -e "$dst" ]]; then
      local backup="$dst.bak.pre-toolkit"
      if [[ $FORCE -ne 1 && $DRY_RUN -ne 1 && -e "$backup" ]]; then
        err "backup already exists: $backup (remove it or pass --force)"
        return 1
      fi
      warn "backing up existing $name to $(basename "$backup")"
      run mv "$dst" "$backup"
    fi

    run mkdir -p "$agent_dir"
    run ln -s "$target" "$dst"
    log "linked: $dst -> $target"
  done
  # Migrate a pre-existing config symlink: the live file is now copy-based.
  local cfg_dst="$agent_dir/config.yml"
  if [[ -L "$cfg_dst" ]]; then
    warn "removing config symlink at $cfg_dst (config is copy-based now)"
    run rm "$cfg_dst"
  fi
  sync_file "$REPO_ROOT/configs/omp/config.yml" "$cfg_dst"
}

# install_claude - link the packages selected in configs/claude/skills.txt into
# Claude Code's user skills directory, one link per skill, so repository edits
# reach the next Claude session. That directory also holds skills the toolkit
# does not own, so only links into this checkout's skills/ are managed. Anything
# else at a selected name is a conflict; --force moves it to a backup directory
# outside skills/, where Claude Code will not load it as a duplicate skill.
install_claude() {
  local config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  local skills_dir="$config_dir/skills"
  local backup_dir="$config_dir/agent-toolkit-backups"
  local skills_root="$REPO_ROOT/skills"
  local selected=() name target dst cur

  while IFS= read -r name || [[ -n "$name" ]]; do
    name="${name%%#*}"
    name="${name//[[:space:]]/}"
    [[ -n "$name" ]] || continue
    if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ || ! -f "$skills_root/$name/SKILL.md" ]]; then
      err "selected skill has no package: skills/$name/SKILL.md"
      return 1
    fi
    selected+=("$name")
  done <"$REPO_ROOT/configs/claude/skills.txt"
  log "linking into $skills_dir (repo: $REPO_ROOT)"

  for name in "${selected[@]+"${selected[@]}"}"; do
    target="$skills_root/$name"
    dst="$skills_dir/$name"
    if [[ -L "$dst" ]]; then
      cur=$(readlink "$dst")
      if [[ "$cur" == "$target" ]]; then
        log "ok (linked): $dst"
        continue
      fi
      if [[ $CHECK -eq 1 ]]; then
        log "differs: $dst -> $cur"
        CONFLICTS=1
        continue
      fi
      if [[ "$cur" != "$skills_root/"* && $FORCE -ne 1 ]]; then
        warn "$dst links to $cur, skipping (use --force to replace)"
        CONFLICTS=1
        continue
      fi
    elif [[ -e "$dst" ]]; then
      if [[ $CHECK -eq 1 ]]; then
        log "differs: $dst is not a toolkit link"
        CONFLICTS=1
        continue
      fi
      if [[ $FORCE -ne 1 ]]; then
        warn "$dst exists and is not a toolkit link, skipping (use --force to move it to $backup_dir)"
        CONFLICTS=1
        continue
      fi
      run mkdir -p "$backup_dir"
      run mv "$dst" "$backup_dir/$name.$(date +%Y%m%d%H%M%S)"
      warn "moved existing $name to $backup_dir"
    elif [[ $CHECK -eq 1 ]]; then
      log "missing: $dst"
      CONFLICTS=1
      continue
    fi
    run mkdir -p "$skills_dir"
    run ln -sfn "$target" "$dst"
    log "linked: $dst -> $target"
  done

  [[ $PRUNE -eq 1 || $CHECK -eq 1 ]] || return 0
  for dst in "$skills_dir"/*; do
    [[ -L "$dst" ]] || continue
    cur=$(readlink "$dst")
    [[ "$cur" == "$skills_root/"* ]] || continue
    name="${dst##*/}"
    if is_selected "$name" "${selected[@]+"${selected[@]}"}"; then
      continue
    fi
    if [[ $CHECK -eq 1 ]]; then
      log "retired: $dst"
      CONFLICTS=1
    else
      run rm "$dst"
      log "pruned: $dst"
    fi
  done
}

is_selected() {
  local name="$1" candidate
  shift
  for candidate in "$@"; do
    [[ "$candidate" == "$name" ]] && return 0
  done
  return 1
}

if [[ "$AGENT" == "claude" ]]; then
  install_claude
else
  install_omp
fi
exit "$CONFLICTS"
