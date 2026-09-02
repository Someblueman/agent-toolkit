# External Tools & Pipeline Composition

Read this guide when building data processing pipelines, integrating tools like `jq`, `awk`, `sed`, `grep`, or `find`, and ensuring streaming efficiency without memory exhaustion.

---

## 1. Pipeline Architecture & Pipefail Semantics

Under standard shell rules, the exit status of a pipeline `cmd1 | cmd2 | cmd3` is determined exclusively by the **last command (`cmd3`)**. If `cmd1` crashes or exits with a fatal error, the pipeline still exits with status `0` if `cmd3` succeeds.

With `set -o pipefail` enabled, the pipeline fails if **any** command in the chain fails:

```bash
set -euo pipefail

# If curl fails (e.g. 404 or connection refused), pipefail ensures the script halts
# instead of feeding empty output into jq and succeeding
curl -sSf "https://api.example.com/data.json" | jq -r '.items[].name'
```

---

## 2. NUL-Delimited Stream Processing (`-print0` & `-0`)

Filenames and file paths on Unix filesystems can contain spaces, tabs, quotes, and even newline characters (every character except `/` and the NUL byte `\0`). Standard line-by-line tools break on such paths.

### The Canonical NUL-Stream Patterns

#### Pattern 1: Batch execution with `find` and `xargs -0`
```bash
# Deletes old log files safely regardless of special characters or whitespace
find /var/log/app -type f -name "*.log" -mtime +30 -print0 | xargs -0 rm -f --
```

#### Pattern 2: Iterative processing with `while read -d ''`
```bash
# Reads NUL-delimited records into a loop without spawning subshells
while IFS= read -r -d '' filepath; do
  [[ -n "$filepath" ]] || continue
  printf 'Inspecting: %s\n' "$filepath"
  gzip -9 -- "$filepath"
done < <(find /data/archives -type f -name "*.tar" -print0)
```

---

## 3. Tool Invocations & Deep Idioms

### 1. `jq` for Structured JSON Processing

Never use `grep`, `sed`, or `awk` to parse JSON. Always use `jq` with defensive parameter passing.

| Idiom / Need | Safe Command / Syntax | Why |
|---|---|---|
| **Raw String Output** | `jq -r '.field'` | Omits enclosing JSON quotes; returns raw text. |
| **Exit on Empty/Null** | `jq -e '.field'` | Exits status `1` if result is `null` or `false`. |
| **Pass Shell Variable** | `jq --arg user "$username" '.users[] \| select(.name == $user)'` | Prevents JSON syntax injection and escaping issues. |
| **Tab-Separated Output** | `jq -r '.[] \| [.id, .email, .role] \| @tsv'` | Safe formatting for consumption by `awk` or `while read`. |

❌ **ANTI-PATTERN: Interpolating shell variables into jq query string**
```bash
# VULNERABLE: Breaks if $search_term contains quotes or JSON syntax
jq ".items[] | select(.name == \"$search_term\")" data.json
```

✅ **PRAGMATIC: Using `--arg` for safe parameter binding**
```bash
jq --arg term "$search_term" '.items[] | select(.name == $term)' data.json
```

---

### 2. `awk` for Columnar Data & Text Aggregation

Use `awk` when manipulating delimited columns, summing values, or filtering structured logs.

#### Rule: Collapse `grep | awk` into a Single `awk` Expression
`awk` natively supports regular expression matching and field splitting. Chaining `grep | awk` wastes process spawns.

❌ **ANTI-PATTERN: Redundant pipeline fork**
```bash
cat /var/log/nginx/access.log | grep " 500 " | awk '{print $1, $7}'
```

✅ **PRAGMATIC: Pure single-pass `awk`**
```bash
awk '$9 == 500 { print $1, $7 }' /var/log/nginx/access.log
```

---

### 3. `sed` for Stream Replacements & Portability

#### 1. Delimiter Safety for Paths and URLs
When substituting filesystem paths or URLs, avoid escaping slashes (`\/`). Use alternate delimiters such as `|`, `#`, or `@`.

```bash
# Clean and readable path substitution using '|'
sed 's|/usr/local/bin|/opt/homebrew/bin|g' config.env
```

#### 2. The `sed -i` Portability Trap (macOS vs GNU Linux)
- **GNU `sed` (Linux)**: Accepts `sed -i 's/foo/bar/g' file.txt`
- **BSD `sed` (macOS)**: Requires an explicit extension argument: `sed -i '' 's/foo/bar/g' file.txt`. Passing no argument or `sed -i` fails.

✅ **PRAGMATIC: Universal In-Place Replacement Pattern**
```bash
replace_in_file() {
  local pattern="$1"
  local replacement="$2"
  local target_file="$3"
  
  local target_dir
  target_dir="$(dirname "$target_file")"
  local tmp_file
  tmp_file="$(mktemp "${target_dir}/sed.tmp.XXXXXX")"
  
  sed "s|${pattern}|${replacement}|g" "$target_file" > "$tmp_file"
  chmod --reference="$target_file" "$tmp_file" 2>/dev/null || chmod 0644 "$tmp_file"
  mv -f "$tmp_file" "$target_file"
}
```

---

### 4. `grep` Conventions & Exit Status

| Flag | Purpose | Recommended Usage |
|---|---|---|
| `-q` / `--quiet` | Suppress output; exit 0 on match, 1 on no match | Use in boolean conditionals: `if grep -q "pattern" file; then` |
| `-E` / `--extended-regexp` | POSIX Extended Regular Expressions (`+`, `?`, `\|`, `()`) | Standardized regex engine across Linux and macOS |
| `-F` / `--fixed-strings` | Treat pattern as exact literal string (no regex overhead) | Fast matching for exact substrings, IPs, or URLs |
| `-v` / `--invert-match` | Invert match to select non-matching lines | Filtering out comments: `grep -vE '^\s*(#\|$)'` |

---

## 4. Streaming vs Memory Exhaustion Discipline

Never load multi-megabyte or gigabyte files into shell variables via command substitution (`var=$(cat file)`). Shell variables are held in memory as null-terminated C strings; large variables severely slow down the shell interpreter and cause Out-Of-Memory (OOM) crashes.

❌ **ANTI-PATTERN: Slurping gigabyte log into memory**
```bash
# Slurps entire 2GB file into memory, causing severe latency and potential OOM crash
log_data=$(cat /var/log/app/huge_server.log)
echo "$log_data" | grep "FATAL" | mail -s "Alert" admin@example.com
```

✅ **PRAGMATIC: Direct stream piping**
```bash
# Constant memory streaming: processes gigabytes in real-time with negligible RAM
grep "FATAL" /var/log/app/huge_server.log | mail -s "Alert" admin@example.com
```
