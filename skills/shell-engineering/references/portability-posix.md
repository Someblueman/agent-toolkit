# POSIX Portability & Shell Dialects

Read this guide when writing scripts targeting POSIX `/bin/sh`, auditing scripts for non-portable bashisms, or ensuring cross-platform execution across macOS (Bash 3.2), Linux (Dash, Bash 5.x), Alpine Linux (BusyBox ash), and BSD systems.

---

## 1. Shebang Hygiene & Target Dialects

The script's shebang line defines its execution contract and permissible syntax:

| Shebang | Intended Environment | Dialect Guarantees & Constraints |
|---|---|---|
| `#!/bin/sh` | Strict POSIX Standard | Must run on Dash (Debian/Ubuntu), Ash (Alpine BusyBox), FreeBSD `sh`, and macOS `/bin/sh`. **Strictly no bashisms permitted.** |
| `#!/usr/bin/env bash` | Portable Bash | Runs on modern Linux (Bash 5.x) and macOS (default Bash 3.2). Avoid Bash 4+ extensions unless explicitly guaranteed by the deployment environment. |
| `#!/bin/bash` | System Bash | May fail if Bash is installed in `/usr/local/bin` or `/opt/homebrew/bin` (e.g. on BSD or customized systems). Prefer `#!/usr/bin/env bash`. |

---

## 2. The Comprehensive Bashism Catalog & POSIX Replacements

When authoring or refactoring scripts with `#!/bin/sh`, consult this catalog to replace non-standard Bash extensions with pure POSIX idioms:

| Feature / Pattern | ❌ Bashism (Fails in `/bin/sh`) | ✅ Pure POSIX Replacement |
|---|---|---|
| **String Test** | `[[ "$a" == "$b" ]]` | `[ "$a" = "$b" ]` (Single bracket, single equals) |
| **Compound Conditions** | `[[ "$a" == "x" && "$b" == "y" ]]` | `[ "$a" = "x" ] && [ "$b" = "y" ]` (Avoid `-a` / `-o` inside `[ ]`) |
| **Regular Expressions** | `[[ "$version" =~ ^v[0-9]+ ]]` | `expr "$version" : '^v[0-9]' >/dev/null` or `printf '%s\n' "$version" \| grep -qE '^v[0-9]'` |
| **Here-Strings** | `grep "pattern" <<< "$text"` | `printf '%s\n' "$text" \| grep "pattern"` |
| **Combined Redirection** | `cmd &> log.txt` | `cmd > log.txt 2>&1` |
| **File Appending** | `cmd &>> log.txt` | `cmd >> log.txt 2>&1` |
| **Echo Formatting** | `echo -n "prompt: "` or `echo -e "a\tb"` | `printf '%s' "prompt: "` or `printf 'a\tb\n'` |
| **Function Declarations** | `function my_func() { ... }` | `my_func() { ... }` (Pure POSIX function syntax) |
| **Command Lookup** | `which binary` or `type -p binary` | `command -v binary >/dev/null 2>&1` |
| **Source Script** | `source ./helpers.sh` | `. ./helpers.sh` (POSIX dot command) |
| **Variable Scoping** | `local my_var="value"` | Note: `local` is non-POSIX (though common). Use subshell `( my_var="value"; ... )` or unset before exit. |
| **Arrays** | `items=("a" "b" "c"); echo "${items[0]}"` | Use positional parameters: `set -- "a" "b" "c"; echo "$1"` |
| **Process Substitution** | `diff <(cmd1) <(cmd2)` | Use temporary files: `f1=$(mktemp); f2=$(mktemp); cmd1 >"$f1"; cmd2 >"$f2"; diff "$f1" "$f2"` |
| **Substring Extraction** | `${str:0:4}` | `printf '%s\n' "$str" \| cut -c1-4` |
| **Case Conversion** | `${str,,}` or `${str^^}` | `printf '%s\n' "$str" \| tr '[:upper:]' '[:lower:]'` |

---

## 3. macOS Bash 3.2 Compatibility Boundary

macOS ships with Bash 3.2 (released in 2006) as the default `/bin/bash` due to Apple's policy against GPLv3 licensed software. If a script uses `#!/usr/bin/env bash`, it must maintain compatibility with Bash 3.2 unless the project explicitly targets newer Bash versions.

### Forbidden Features in macOS-Compatible Bash Scripts

| Forbidden Bash 4+ Feature | Introduced In | Why It Fails on macOS | Portable Alternative |
|---|---|---|---|
| **Associative Arrays** (`declare -A map`) | Bash 4.0 | Syntax error on Bash 3.2 | Use `jq`, `awk`, or delegate state to Python. |
| **`readarray` / `mapfile`** | Bash 4.0 | Command not found on Bash 3.2 | Use `while IFS= read -r line; do ... done` loop. |
| **Case Parameter Modification** (`${var,,}`) | Bash 4.0 | Bad substitution error | Use `tr '[:upper:]' '[:lower:]'` or `awk '{print tolower($0)}'`. |
| **Globstar Directory Traversal** (`**/*.sh`) | Bash 4.0 | Fails or matches literally `**` | Use `find . -type f -name "*.sh"`. |
| **Built-in `printf` Date Formatting** (`%(%Y)T`) | Bash 4.2 | Unsupported format specifier | Use standard external `date -u +'%Y-%m-%d'`. |
| **Negative String Offsets** (`${str: -3}`) | Bash 4.2 | Unpredictable parsing on old versions | Compute length first: `len=${#str}; echo "${str:$((len - 3))}"`. |

---

## 4. POSIX Standard Parameter Expansions

Pure POSIX shell provides powerful, standardized parameter expansions that work identically across all compliant shells without spawning external subshells:

```sh
# 1. Default Value Fallback (if unset or null)
PORT="${SERVER_PORT:-8080}"

# 2. Assign Default Value (if unset or null)
: "${CONFIG_FILE:="/etc/app/config.json"}"

# 3. Error if Unset or Null
: "${DATABASE_URL:?Database connection URL must be provided}"

# 4. Use Alternate Value (if set and not null)
IS_DEBUG="${DEBUG:+"--verbose"}"

# 5. String Length
STRING_LENGTH="${#MY_VARIABLE}"

# 6. Remove Smallest Prefix Pattern (#)
FILE_PATH="/var/log/app/service.log"
RELATIVE="${FILE_PATH#/var/log/}" # Result: "app/service.log"

# 7. Remove Longest Prefix Pattern (##)
BASE_FILENAME="${FILE_PATH##*/}" # Result: "service.log"

# 8. Remove Smallest Suffix Pattern (%)
EXTENSION_STRIPPED="${BASE_FILENAME%.log}" # Result: "service"

# 9. Remove Longest Suffix Pattern (%%)
ARCHIVE="backup.tar.gz"
ROOT_NAME="${ARCHIVE%%.*}" # Result: "backup"
```

---

## 5. Concrete Code Comparisons

### Example 1: POSIX Script Checking Executable and Parsing Flag

❌ **ANTI-PATTERN: Non-portable bashisms in `#!/bin/sh`**
```sh
#!/bin/sh
# Broken: uses bashisms inside a POSIX shebang

function check_prereqs() {
  if which jq &> /dev/null; then
    echo -e "jq is installed\n"
  else
    echo "Error: jq missing" && exit 1
  fi
}

check_prereqs
```

✅ **PRAGMATIC: Clean, compliant POSIX `/bin/sh` implementation**
```sh
#!/bin/sh
set -eu

check_prereqs() {
  if command -v jq >/dev/null 2>&1; then
    printf 'jq is installed\n'
  else
    printf 'error: jq is required but not installed in PATH\n' >&2
    exit 1
  fi
}

check_prereqs
```

---

### Example 2: Parsing Lines into List (Bash 3.2 Compatible)

❌ **ANTI-PATTERN: Bash 4+ `readarray` breaking on macOS**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Fails on macOS default Bash 3.2 with "readarray: command not found"
readarray -t services < <(docker ps --format '{{.Names}}')
for svc in "${services[@]}"; do
  echo "Monitoring $svc"
done
```

✅ **PRAGMATIC: Stream processing compatible with Bash 3.2 and modern Bash**
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

services=()
while IFS= read -r svc; do
  [[ -n "$svc" ]] || continue
  services+=("$svc")
done < <(docker ps --format '{{.Names}}')

for svc in "${services[@]}"; do
  printf 'Monitoring %s\n' "$svc"
done
```
