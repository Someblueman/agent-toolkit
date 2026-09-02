# Defensive Quoting, Paths, & CLI Parsing

Read this guide when expanding variables, handling paths with whitespace and special characters, traversing directories, or building robust command-line argument parsers using `getopts`.

---

## 1. The Golden Quoting Rules

Unquoted parameter expansions are the #1 source of severe vulnerabilities, data corruption, and silent logic bugs in shell scripts. When an unquoted variable is expanded, the shell performs **word splitting** (breaking strings on `$IFS` whitespace) and **pathname expansion (globbing)** on the contents.

### The Quoting Invariants

| Expansion | Behavior / Result | Safety Verdict |
|---|---|---|
| `"$var"` | Preserves literal string, all whitespace, tabs, and newlines. No globbing occurs. | ✅ **Mandatory Default** |
| `$var` | Splits value into multiple arguments on whitespace; expands any `*`, `?`, `[` wildcards. | ❌ **Strictly Forbidden** (except intentional splitting) |
| `"$@"` | Expands to distinct, quoted positional arguments: `"$1"` `"$2"` `"$3"` ... | ✅ **Mandatory for Argument Forwarding** |
| `"$*"` | Joins all arguments into a SINGLE concatenated string: `"$1 $2 $3"` | ⚠️ **Use only for concatenated output/logging** |
| `$*` or `$@` | Splits every argument across whitespace and expands glob wildcards. | ❌ **Strictly Forbidden** |

---

## 2. Globbing & Path Safety Invariants

### 1. The Leading Hyphen Vulnerability
If a filename starts with a hyphen (e.g. `-rf` or `--help`), passing it directly to a command like `rm $file` or `cat $file` can cause the command to interpret the filename as a CLI flag.

#### Defensive Measures:
- **Prefix relative globs with `./`**: Always use `./*.txt` instead of `*.txt`.
- **Use the `--` end-of-options marker**: `rm -f -- "$filename"`.

### 2. The Empty Directory Glob Pitfall
If no files match a glob (e.g. `for f in ./*.txt`), the shell leaves the literal unexpanded glob string (`./*.txt`) in the loop variable unless `nullglob` is enabled.

✅ **PRAGMATIC: Checking existence before processing**
```bash
for file in ./*.txt; do
  # Guard against literal pattern when no matches exist
  [[ -e "$file" ]] || continue
  printf 'Processing file: %s\n' "$file"
done
```

### 3. Never Parse `ls` Output
Parsing `ls` output with `for f in $(ls)` breaks on spaces, newlines, tabs, and special characters.

❌ **ANTI-PATTERN: Iterating over `ls`**
```bash
# BROKEN: Splits "Quarterly Report 2026.pdf" into 3 separate words!
for file in $(ls *.pdf); do
  process_file "$file"
done
```

✅ **PRAGMATIC: Direct glob expansion or `find -print0`**
```bash
for file in ./*.pdf; do
  [[ -e "$file" ]] || continue
  process_file "$file"
done
```

---

## 3. Robust Script Directory Resolution

Scripts must reliably locate adjacent configuration files, templates, or helper scripts regardless of the current working directory from which the user invoked the script.

```bash
# Robust, canonical script directory resolution:
# 1. Uses BASH_SOURCE[0] if running in Bash, falls back to $0 in POSIX sh
# 2. Changes to the directory in a subshell to resolve symlinks with pwd -P
# 3. Suppresses stdout and stderr from cd
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd -P)"
```

---

## 4. Robust CLI Argument Parsing with `getopts`

For scripts accepting command-line flags and options, use the POSIX standard `getopts` built-in. Do not manually parse `$1`, `$2` in ad-hoc loops when standard options are needed.

### Canonical `getopts` Implementation Template

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

readonly SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF >&2
Usage: ${SCRIPT_NAME} [OPTIONS] <input_file>

Options:
  -c, --config <path>   Path to configuration file (required)
  -o, --output <path>   Destination output path (default: dist/out.bin)
  -v, --verbose         Enable verbose diagnostic logging
  -h, --help            Show this help message and exit

Arguments:
  input_file            Source data file to process
EOF
}

main() {
  local config_file=""
  local output_path="dist/out.bin"
  local verbose=0

  # Note leading colon ':': activates silent error reporting mode
  # Options followed by ':' require an argument (e.g. c: and o:)
  while getopts ":c:o:vh-:" opt; do
    case "$opt" in
      c)
        config_file="$OPTARG"
        ;;
      o)
        output_path="$OPTARG"
        ;;
      v)
        verbose=1
        ;;
      h)
        usage
        exit 0
        ;;
      -)
        # Handle long options (--config, --output, --verbose, --help)
        case "$OPTARG" in
          config)
            config_file="${!OPTIND}"
            OPTIND=$((OPTIND + 1))
            ;;
          config=*)
            config_file="${OPTARG#*=}"
            ;;
          output)
            output_path="${!OPTIND}"
            OPTIND=$((OPTIND + 1))
            ;;
          output=*)
            output_path="${OPTARG#*=}"
            ;;
          verbose)
            verbose=1
            ;;
          help)
            usage
            exit 0
            ;;
          *)
            printf 'error: unknown long option --%s\n' "$OPTARG" >&2
            usage
            exit 2
            ;;
        esac
        ;;
      :)
        printf 'error: option -%s requires an argument.\n' "$OPTARG" >&2
        usage
        exit 2
        ;;
      \?)
        printf 'error: unrecognized option -%s\n' "$OPTARG" >&2
        usage
        exit 2
        ;;
    esac
  done

  # Shift away parsed options, leaving positional arguments
  shift $((OPTIND - 1))

  # Validate required options and positional arguments
  if [[ -z "$config_file" ]]; then
    printf 'error: mandatory option -c/--config is missing.\n' >&2
    usage
    exit 2
  fi

  if [[ $# -ne 1 ]]; then
    printf 'error: exactly one input file argument is required, received %d.\n' "$#" >&2
    usage
    exit 2
  fi

  local input_file="$1"

  if [[ ! -f "$input_file" ]]; then
    printf 'error: input file "%s" does not exist or is not a regular file.\n' "$input_file" >&2
    exit 1
  fi

  if [[ "$verbose" -eq 1 ]]; then
    printf 'Processing "%s" with config "%s" -> "%s"\n' "$input_file" "$config_file" "$output_path"
  fi
}

main "$@"
```

---

## 5. Defensive Quoting Anti-Patterns & Pragmatic Solutions

| Anti-Pattern | Vulnerability / Failure Mode | Pragmatic Replacement |
|---|---|---|
| `rm -rf $target_dir` | If `$target_dir` is empty/unset, executes `rm -rf /` or deletes current directory. | `rm -rf -- "${target_dir:?Target directory variable is unset}"` |
| `cd $dir` | Fails on directories with spaces (e.g. `My Documents`). | `cd -- "$dir" \|\| exit 1` |
| `ssh host "cmd $arg"` | Variable expanded locally; shell injection if `$arg` contains quotes or semicolons. | Pass via stdin or use `printf %q`: `ssh host "$(printf 'cmd %q' "$arg")"` |
| `cat $files` | Fails when filenames contain spaces or glob patterns. | `cat -- "${files[@]}"` |
| `eval "$user_input"` | Remote code execution vulnerability. | Never use `eval` with untrusted input; use arrays or direct function invocation. |
