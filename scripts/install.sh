#!/usr/bin/env bash
# Stable CLI entrypoint: Codex materialization uses Python; OMP keeps its links.
set -euo pipefail
IFS=$'\n\t'
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  echo "Usage: $0 <codex|omp> [--force] [--dry-run] [--prune] [--check]"
  echo "Codex: --check verifies content; --prune removes retired managed items only."
  echo "OMP: supports --force and --dry-run. Requires existing config drift review."
}

[[ $# -gt 0 ]] || { usage; exit 2; }
if [[ "$1" == "--help" || "$1" == "-h" ]]; then usage; exit 0; fi
AGENT="$1"
shift
if [[ "$AGENT" == "codex" ]]; then
  exec python3 "$REPO_ROOT/scripts/install_codex.py" "$@"
fi
[[ "$AGENT" == "omp" ]] || { usage; exit 2; }
FORCE=0
DRY_RUN=0
CONFLICTS=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --help|-h) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

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

install_omp
exit "$CONFLICTS"
