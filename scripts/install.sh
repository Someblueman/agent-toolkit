#!/usr/bin/env bash
# install.sh - install this toolkit's shared content into a target agent's home.
#
# Usage: install.sh <agent> [--force] [--dry-run] [--prune]
#
# Agents supported: codex
#
# Behavior:
#   - Each shared skill is materialized as a real directory at
#     ~/.codex/skills/<name>/ with files copied from skills/<name>/.
#   - The Codex interface metadata (openai.yaml) is placed at
#     ~/.codex/skills/<name>/agents/openai.yaml so Codex's skill picker can read it.
#     Source: configs/codex/skills/<name>/openai.yaml.
#   - The Codex-specific engineering policy is installed as ~/.codex/AGENTS.md.
#     Source: configs/codex/AGENTS.md.
#   - The anti-bloat enforcement script is installed as ~/.codex/scripts/check_anti_bloat.py.
#
# Drift policy: if a target file/dir already exists and differs from the repo copy, the
# install prints a warning and skips that item. Pass --force to replace it.
#
# Skills present in ~/.codex/skills/ but absent from the repo are left alone. Pass
# --prune to remove them.

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 <agent> [--force] [--dry-run] [--prune]

Agents:
  codex    Install into ~/.codex/

Options:
  --force    Replace existing files/dirs that differ from the repo (default: warn and skip).
  --dry-run  Print planned actions without touching the filesystem.
  --prune    Remove skills at the target that no longer exist in the repo (default: leave alone).
  -h, --help Show this help.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

AGENT=""
FORCE=0
DRY_RUN=0
PRUNE=0

for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --prune) PRUNE=1 ;;
    -*) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
    *)
      if [[ -z "$AGENT" ]]; then AGENT="$arg"
      else echo "Unexpected argument: $arg" >&2; usage; exit 1
      fi
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

log()  { printf '[install] %s\n' "$*"; }
warn() { printf '[install] WARN: %s\n' "$*" >&2; }
err()  { printf '[install] ERROR: %s\n' "$*" >&2; }

# Hash a file (sha256) or, for a directory, the canonical form of the file list.
# Returns 0 with content on stdout.
hash_file()  { shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'; }
hash_dir()   {
  # Stable hash of the directory's file contents (path + sha256 per file).
  ( cd "$1" && find . -type f -not -path '*/__pycache__/*' | LC_ALL=C sort | while read -r f; do
      printf '%s\t%s\n' "$f" "$(shasum -a 256 "$f" | awk '{print $1}')"
    done ) | shasum -a 256 | awk '{print $1}'
}

# Run a shell action unless --dry-run.
run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '  DRY-RUN: %s\n' "$*"
  else
    eval "$@"
  fi
}

# sync_file <src> <dst> -- copy src -> dst if dst missing, identical, or --force.
sync_file() {
  local src="$1" dst="$2"
  if [[ ! -f "$src" ]]; then err "source missing: $src"; return 1; fi
  if [[ -L "$dst" ]]; then
    if [[ $FORCE -eq 1 ]]; then
      warn "removing symlink at $dst (force)"
      run "rm '$dst'"
    else
      warn "symlink at $dst, skipping (use --force to replace)"
      return 0
    fi
  fi
  if [[ -f "$dst" ]]; then
    if cmp -s "$src" "$dst"; then
      log "ok (unchanged): $dst"
      return 0
    fi
    if [[ $FORCE -eq 1 ]]; then
      warn "drift at $dst, replacing (force)"
      run "rm '$dst'"
    else
      warn "drift at $dst, skipping (use --force to replace)"
      return 0
    fi
  fi
  run "mkdir -p '$(dirname "$dst")'"
  run "cp '$src' '$dst'"
  log "copied: $dst"
}

# sync_skill <name> <skills_dir> <adapter_dir> <target_skills_dir>
# Materializes <skills_dir>/<name> + <adapter_dir>/<name>/openai.yaml into
# <target_skills_dir>/<name>/, including the agents/ subdir.
sync_skill() {
  local name="$1" skills_dir="$2" adapter_dir="$3" target_dir="$4"
  local src_skill="$skills_dir/$name"
  local target_skill="$target_dir/$name"

  if [[ ! -d "$src_skill" ]]; then err "skill source missing: $src_skill"; return 1; fi

  if [[ -L "$target_skill" ]]; then
    if [[ $FORCE -eq 1 ]]; then
      warn "removing symlink at $target_skill (force)"
      run "rm '$target_skill'"
    else
      warn "symlink at $target_skill, skipping (use --force to replace)"
      return 0
    fi
  fi

  # Decide: does the existing target dir match the repo's source?
  local drift=0
  if [[ -d "$target_skill" && ! -L "$target_skill" ]]; then
    local src_h tgt_h
    src_h=$(hash_dir "$src_skill")
    tgt_h=$(hash_dir "$target_skill")
    if [[ "$src_h" != "$tgt_h" ]]; then drift=1; fi
  elif [[ ! -e "$target_skill" ]]; then
    drift=0  # nothing there yet
  else
    drift=1  # something weird (file, broken link)
  fi

  if [[ $drift -eq 1 && -e "$target_skill" && $FORCE -ne 1 ]]; then
    warn "drift at $target_skill, skipping (use --force to replace)"
    return 0
  fi

  if [[ $drift -eq 1 ]]; then
    warn "drift at $target_skill, replacing (force)"
    run "rm -rf '$target_skill'"
  fi

  # Copy the skill body.
  run "mkdir -p '$target_skill'"
  # rsync-style: copy file tree excluding noisy artifacts.
  run "tar -C '$skills_dir' --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' -cf - '$name' | tar -C '$target_dir' -xf -"

  # Per-skill Codex metadata: <skill>/agents/openai.yaml
  local adapter_src="$adapter_dir/$name/openai.yaml"
  local adapter_dst="$target_skill/agents/openai.yaml"
  if [[ -f "$adapter_src" ]]; then
    sync_file "$adapter_src" "$adapter_dst"
  else
    # No adapter: ensure agents/ is empty (or absent). Nothing to do.
    log "no adapter for $name (ok)"
  fi
}

install_codex() {
  local home="${CODEX_HOME:-$HOME/.codex}"
  local skills_dir="$REPO_ROOT/skills"
  local adapter_dir="$REPO_ROOT/configs/codex/skills"
  local target_skills_dir="$home/skills"

  log "installing into $home (repo: $REPO_ROOT)"

  # Codex engineering policy -> AGENTS.md
  sync_file "$REPO_ROOT/configs/codex/AGENTS.md" "$home/AGENTS.md"

  # Skills
  for skill_dir in "$skills_dir"/*/; do
    [[ -d "$skill_dir" ]] || continue
    local name
    name=$(basename "$skill_dir")
    sync_skill "$name" "$skills_dir" "$adapter_dir" "$target_skills_dir"
  done

  # Anti-bloat script
  local anti_bloat="$REPO_ROOT/skills/pragmatic-engineering/scripts/check_anti_bloat.py"
  if [[ -f "$anti_bloat" ]]; then
    sync_file "$anti_bloat" "$home/scripts/check_anti_bloat.py"
    if [[ $DRY_RUN -eq 0 ]]; then
      chmod +x "$home/scripts/check_anti_bloat.py"
    fi
  fi

  # Optionally prune skills that no longer exist in the repo.
  if [[ $PRUNE -eq 1 && -d "$target_skills_dir" ]]; then
    for entry in "$target_skills_dir"/*/; do
      [[ -d "$entry" ]] || continue
      local name
      name=$(basename "$entry")
      # Skip Codex-managed directories.
      [[ "$name" == ".system" || "$name" == ".hidden" ]] && continue
      if [[ ! -d "$skills_dir/$name" ]]; then
        if [[ $FORCE -eq 1 || $DRY_RUN -eq 1 ]]; then
          warn "pruning $entry (no longer in repo)"
          run "rm -rf '$entry'"
        else
          warn "stale: $entry (use --prune --force to remove)"
        fi
      fi
    done
  fi
}

case "$AGENT" in
  codex) install_codex ;;
  *) err "unsupported agent: $AGENT (supported: codex)"; usage; exit 1 ;;
esac

log "done."
