#!/usr/bin/env bash

set -u
set -o pipefail

usage() {
  cat <<'USAGE'
Usage: haskell_quality_check.sh [options] [path]

Repository-agnostic fallback checks for Haskell projects.

Options:
  --fix                         Format source files in place
  --strict                      Exit 3 when a requested check is skipped
  --tool=auto|cabal|stack       Select build authority (default: auto)
  --formatter=auto|fourmolu|ormolu|none
                                Select formatter (default: auto)
  --no-format                   Disable formatting check
  --no-hlint                    Disable HLint
  --no-build                    Disable build
  --no-test                     Disable tests
  --haddock                     Run Haddock
  --package-check               Run cabal check in each Cabal package directory
  -h, --help                    Show this help

Auto tool selection refuses mixed Cabal/Stack surfaces. The script never installs
tools. Its final summary distinguishes passed, failed, and skipped checks.
Benchmarks and clean source-archive release checks remain repository-specific and
are intentionally outside this fallback.

Exit status:
  0  no observed failure (inspect skipped count unless --strict was used)
  1  at least one check failed
  2  usage or path error
  3  --strict and at least one requested check was skipped
USAGE
}

fix=0
strict=0
tool_choice="auto"
formatter_choice="auto"
run_format=1
run_hlint=1
run_build=1
run_tests=1
run_haddock=0
run_package_check=0
root="."
root_seen=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --fix) fix=1 ;;
    --strict) strict=1 ;;
    --tool=auto|--tool=cabal|--tool=stack) tool_choice=${1#--tool=} ;;
    --formatter=auto|--formatter=fourmolu|--formatter=ormolu|--formatter=none)
      formatter_choice=${1#--formatter=}
      ;;
    --no-format) run_format=0 ;;
    --no-hlint) run_hlint=0 ;;
    --no-build) run_build=0 ;;
    --no-test) run_tests=0 ;;
    --haddock) run_haddock=1 ;;
    --package-check) run_package_check=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [ "$root_seen" -eq 1 ]; then
        echo "Only one path may be supplied." >&2
        usage >&2
        exit 2
      fi
      root=$1
      root_seen=1
      ;;
  esac
  shift
done

if ! cd "$root"; then
  exit 2
fi

passed=0
failed=0
skipped=0

requested_checks=$((run_hlint + run_build + run_tests + run_haddock + run_package_check))
if [ "$run_format" -eq 1 ] && [ "$formatter_choice" != "none" ]; then
  requested_checks=$((requested_checks + 1))
fi

have() {
  command -v "$1" >/dev/null 2>&1
}

print_command() {
  printf '  +'
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
}

pass_check() {
  passed=$((passed + 1))
  printf 'PASS  %s\n' "$1"
}

fail_check() {
  failed=$((failed + 1))
  printf 'FAIL  %s (exit %s)\n' "$1" "$2" >&2
}

skip_check() {
  skipped=$((skipped + 1))
  printf 'SKIP  %s: %s\n' "$1" "$2"
}

note() {
  printf 'NOTE  %s\n' "$1"
}

run_check() {
  label=$1
  shift
  printf 'CHECK %s\n' "$label"
  print_command "$@"
  "$@"
  code=$?
  if [ "$code" -eq 0 ]; then
    pass_check "$label"
  else
    fail_check "$label" "$code"
  fi
}

run_check_in_dir() {
  label=$1
  directory=$2
  shift 2
  printf 'CHECK %s\n' "$label"
  printf '  in %q\n' "$directory"
  print_command "$@"
  (cd "$directory" && "$@")
  code=$?
  if [ "$code" -eq 0 ]; then
    pass_check "$label"
  else
    fail_check "$label" "$code"
  fi
}

collect_haskell_files() {
  if have git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git ls-files -co --exclude-standard -z -- '*.hs' '*.lhs'
  else
    find . \
      -type d \( -name .git -o -name dist-newstyle -o -name .stack-work \
         -o -name vendor -o -name vendored -o -name generated -o -name autogen \) -prune \
      -o \( -name '*.hs' -o -name '*.lhs' \) -type f -print0
  fi
}

collect_cabal_files() {
  find . \
    -type d \( -name .git -o -name dist-newstyle -o -name .stack-work \
       -o -name vendor -o -name vendored -o -name generated -o -name autogen \) -prune \
    -o -name '*.cabal' -type f -print0
}

safe_to_format_in_place() {
  case "$1" in
    vendor/*|*/vendor/*|vendored/*|*/vendored/*|generated/*|*/generated/*|autogen/*|*/autogen/*)
      return 1
      ;;
    *) return 0 ;;
  esac
}

source_files=()
source_file_count=0
while IFS= read -r -d '' file; do
  source_files+=("$file")
  source_file_count=$((source_file_count + 1))
done < <(collect_haskell_files)

format_files=()
format_file_count=0
excluded_from_fix=0
if [ "$source_file_count" -gt 0 ]; then
  for file in "${source_files[@]}"; do
    if [ "$fix" -eq 1 ] && ! safe_to_format_in_place "$file"; then
      excluded_from_fix=$((excluded_from_fix + 1))
    else
      format_files+=("$file")
      format_file_count=$((format_file_count + 1))
    fi
  done
fi

selected_formatter="$formatter_choice"
if [ "$run_format" -eq 1 ] && [ "$selected_formatter" = "auto" ]; then
  has_fourmolu_config=0
  has_ormolu_config=0
  if [ -f .fourmolu.yaml ] || [ -f fourmolu.yaml ]; then
    has_fourmolu_config=1
  fi
  if [ -f .ormolu ]; then
    has_ormolu_config=1
  fi

  if [ "$has_fourmolu_config" -eq 1 ] && [ "$has_ormolu_config" -eq 1 ]; then
    selected_formatter="ambiguous"
  elif [ "$has_fourmolu_config" -eq 1 ]; then
    selected_formatter="fourmolu"
  elif [ "$has_ormolu_config" -eq 1 ]; then
    selected_formatter="ormolu"
  elif have fourmolu && ! have ormolu; then
    selected_formatter="fourmolu"
  elif have ormolu && ! have fourmolu; then
    selected_formatter="ormolu"
  elif have fourmolu && have ormolu; then
    selected_formatter="ambiguous"
  else
    selected_formatter="unavailable"
  fi
fi

if [ "$run_format" -eq 1 ] && [ "$formatter_choice" != "none" ]; then
  if [ "$source_file_count" -eq 0 ]; then
    skip_check "formatter" "no tracked or nonignored Haskell source files found"
  elif [ "$selected_formatter" = "ambiguous" ]; then
    skip_check "formatter" "formatter intent is ambiguous; use --formatter=fourmolu or --formatter=ormolu"
  elif [ "$selected_formatter" = "unavailable" ]; then
    skip_check "formatter" "Fourmolu and Ormolu are unavailable"
  elif ! have "$selected_formatter"; then
    skip_check "formatter" "$selected_formatter is unavailable"
  elif [ "$format_file_count" -eq 0 ]; then
    skip_check "formatter" "all source files were excluded from in-place formatting as generated or vendored"
  else
    if [ "$fix" -eq 1 ]; then
      run_check "$selected_formatter format" "$selected_formatter" --mode inplace "${format_files[@]}"
      if [ "$excluded_from_fix" -gt 0 ]; then
        note "$excluded_from_fix generated or vendored source file(s) intentionally excluded from in-place formatting"
      fi
    else
      run_check "$selected_formatter check" "$selected_formatter" --mode check "${format_files[@]}"
    fi
  fi
fi

if [ "$run_hlint" -eq 1 ]; then
  if [ "$source_file_count" -eq 0 ]; then
    skip_check "HLint" "no tracked or nonignored Haskell source files found"
  elif ! have hlint; then
    skip_check "HLint" "hlint is unavailable"
  else
    run_check "HLint ($source_file_count tracked/nonignored source files)" hlint "${source_files[@]}"
  fi
fi

cabal_files=()
cabal_file_count=0
while IFS= read -r -d '' file; do
  cabal_files+=("$file")
  cabal_file_count=$((cabal_file_count + 1))
done < <(collect_cabal_files)

has_cabal_surface=0
has_stack_surface=0
cabal_workdir="."
cabal_layout_problem=""
if [ -f cabal.project ]; then
  has_cabal_surface=1
elif [ "$cabal_file_count" -eq 1 ]; then
  has_cabal_surface=1
  cabal_workdir=$(dirname "${cabal_files[0]}")
elif [ "$cabal_file_count" -gt 1 ]; then
  has_cabal_surface=1
  cabal_layout_problem="multiple Cabal package files without a root cabal.project; package aggregation is ambiguous"
fi
if [ -f stack.yaml ]; then
  has_stack_surface=1
fi

selected_tool="$tool_choice"
tool_problem=""
if [ "$selected_tool" = "auto" ]; then
  if [ "$has_cabal_surface" -eq 1 ] && [ "$has_stack_surface" -eq 1 ]; then
    selected_tool="none"
    tool_problem="mixed Cabal and Stack surfaces; inspect repository authority or pass --tool"
  elif [ "$has_stack_surface" -eq 1 ]; then
    selected_tool="stack"
  elif [ "$has_cabal_surface" -eq 1 ]; then
    selected_tool="cabal"
  else
    selected_tool="none"
    tool_problem="no Cabal or Stack project surface found"
  fi
elif [ "$selected_tool" = "cabal" ] && [ "$has_cabal_surface" -eq 0 ]; then
  selected_tool="none"
  tool_problem="--tool=cabal selected but no Cabal project surface was found"
elif [ "$selected_tool" = "stack" ] && [ "$has_stack_surface" -eq 0 ]; then
  selected_tool="none"
  tool_problem="--tool=stack selected but no stack.yaml was found"
fi

if [ "$selected_tool" = "cabal" ] && [ -n "$cabal_layout_problem" ]; then
  selected_tool="none"
  tool_problem="$cabal_layout_problem"
fi

build_tool_ready=1
if [ "$selected_tool" = "none" ]; then
  build_tool_ready=0
elif ! have "$selected_tool"; then
  build_tool_ready=0
  tool_problem="$selected_tool is unavailable"
fi

if [ "$run_build" -eq 1 ]; then
  if [ "$build_tool_ready" -eq 0 ]; then
    skip_check "build" "$tool_problem"
  elif [ "$selected_tool" = "cabal" ]; then
    run_check_in_dir "Cabal build" "$cabal_workdir" cabal build all
  else
    run_check "Stack build" stack build --test --no-run-tests
  fi
fi

if [ "$run_tests" -eq 1 ]; then
  if [ "$build_tool_ready" -eq 0 ]; then
    skip_check "tests" "$tool_problem"
  elif [ "$selected_tool" = "cabal" ]; then
    run_check_in_dir "Cabal tests" "$cabal_workdir" cabal test all
  else
    run_check "Stack tests" stack test
  fi
fi

if [ "$run_haddock" -eq 1 ]; then
  if [ "$build_tool_ready" -eq 0 ]; then
    skip_check "Haddock" "$tool_problem"
  elif [ "$selected_tool" = "cabal" ]; then
    run_check_in_dir "Cabal Haddock" "$cabal_workdir" cabal haddock all
  else
    run_check "Stack Haddock" stack haddock
  fi
fi

if [ "$run_package_check" -eq 1 ]; then
  if [ "$cabal_file_count" -eq 0 ]; then
    skip_check "cabal check" "no Cabal package file found"
  elif ! have cabal; then
    skip_check "cabal check" "cabal is unavailable"
  else
    checked_directories=""
    if [ "$cabal_file_count" -gt 0 ]; then
      for file in "${cabal_files[@]}"; do
        directory=$(dirname "$file")
        case "
$checked_directories
" in
          *"
$directory
"*) continue ;;
        esac
        checked_directories="${checked_directories}${checked_directories:+
}${directory}"
        run_check_in_dir "cabal check ($directory)" "$directory" cabal check
      done
    fi
  fi
fi

if [ "$requested_checks" -eq 0 ]; then
  skip_check "quality pass" "no checks requested"
fi

printf '\nRESULT '
if [ "$failed" -gt 0 ]; then
  printf 'fail'
  exit_code=1
elif [ "$strict" -eq 1 ] && [ "$skipped" -gt 0 ]; then
  printf 'incomplete'
  exit_code=3
else
  printf 'pass'
  exit_code=0
fi
printf ' passed=%s failed=%s skipped=%s tool=%s formatter=%s\n' \
  "$passed" "$failed" "$skipped" "$selected_tool" "$selected_formatter"

exit "$exit_code"
