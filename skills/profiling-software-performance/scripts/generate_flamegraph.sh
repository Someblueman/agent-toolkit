#!/usr/bin/env bash
# generate_flamegraph.sh - Cross-platform Flamegraph Generator
# Converts Linux perf script output, folded stacks, or macOS sample outputs into interactive SVG flamegraphs.
#
# Usage:
#   ./generate_flamegraph.sh [OPTIONS] <input_file> <output.svg>
#
# Options:
#   --title "Title Text"    Custom title header for SVG (default: "Flame Graph")
#   --color "warm|io|mem"   Color palette: warm (default/on-CPU), io (blue/off-CPU), mem (green/heap)
#   --width 1200            Width of the generated SVG in pixels (default: 1200)

set -euo pipefail

TITLE="Flame Graph"
COLOR_PALETTE="warm"
SVG_WIDTH=1200
INPUT_FILE=""
OUTPUT_FILE=""

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <input_file> <output_file.svg>

Arguments:
  input_file         Path to perf script log, macOS sample output, or collapsed stack file (.folded)
  output_file.svg    Path to destination SVG file

Options:
  --title TITLE      Title shown on the SVG banner (default: "Flame Graph")
  --color PALETTE    Color scheme: 'warm' (on-CPU), 'io' (off-CPU/blue), 'mem' (green)
  --width PIXELS     SVG canvas width in pixels (default: 1200)
  -h, --help         Show this help message

Supported input formats:
  - Folded stack lines: 'funcA;funcB;funcC 142'
  - Linux perf script output
  - macOS sample output
EOF
}

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --title)
            TITLE="$2"
            shift 2
            ;;
        --color)
            COLOR_PALETTE="$2"
            shift 2
            ;;
        --width)
            SVG_WIDTH="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            if [[ -z "$INPUT_FILE" ]]; then
                INPUT_FILE="$1"
            elif [[ -z "$OUTPUT_FILE" ]]; then
                OUTPUT_FILE="$1"
            else
                echo "Error: Unexpected argument '$1'" >&2
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$INPUT_FILE" || -z "$OUTPUT_FILE" ]]; then
    echo "Error: Input and Output file paths are required." >&2
    show_help
    exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: Input file '$INPUT_FILE' does not exist." >&2
    exit 1
fi

# Create temporary directory for intermediate files
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

COLLAPSED_STACKS="$TMP_DIR/collapsed.txt"

# Step 1: Detect format and normalize to collapsed/folded stack format: "stack;trace;line count"
python3 - << 'PY_PARSER_EOF' "$INPUT_FILE" "$COLLAPSED_STACKS"
import sys
import re

in_path = sys.argv[1]
out_path = sys.argv[2]

with open(in_path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Check if input is already folded stacks (e.g. "foo;bar;baz 123")
is_folded = True
for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    parts = line.rsplit(' ', 1)
    if len(parts) != 2 or not parts[1].isdigit():
        is_folded = False
        break

if is_folded:
    with open(out_path, 'w', encoding='utf-8') as out:
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                out.write(line + '\n')
    sys.exit(0)

# Check if macOS sample output
is_macos_sample = any("Call graph:" in l or "Sort by top of stack" in l for l in lines[:50])

if is_macos_sample:
    # Basic parser for macOS sample hierarchical tree
    stacks = []
    current_stack = []
    with open(out_path, 'w', encoding='utf-8') as out:
        in_call_graph = False
        for line in lines:
            if "Call graph:" in line:
                in_call_graph = True
                continue
            if in_call_graph:
                if line.startswith("Total number in stack") or line.startswith("Sort by"):
                    break
                # macOS sample format: " + 1422 Thread_1234 (process_name) [0x123]"
                match = re.search(r'^\s*[\+\:\!\|\s]+(\d+)\s+(.+?)(?:\s+\(in\s+.+?\))?(?:\s+\[.+?\])?$', line)
                if match:
                    count_str, func_name = match.groups()
                    count = int(count_str)
                    func_clean = re.sub(r'\(in.*?\)', '', func_name).strip()
                    func_clean = re.sub(r'\[.*?\]', '', func_clean).strip()
                    if func_clean:
                        out.write(f"process;{func_clean} {count}\n")
    sys.exit(0)

# Default: Linux perf script parser
stack = []
current_sample_weight = 1
collapsed_dict = {}

for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        if stack:
            key = ";".join(reversed(stack))
            collapsed_dict[key] = collapsed_dict.get(key, 0) + current_sample_weight
            stack = []
        continue
    # perf script line with instruction pointer: "ffffffff810643b0 native_write_msr ([kernel.kallsyms])"
    match = re.search(r'^\s*[0-9a-fA-F]+\s+(.+?)(?:\s+\(.*\))?$', line)
    if match:
        func = match.group(1).split('+')[0].strip()
        stack.append(func)
    elif stack:
        # End of stack
        key = ";".join(reversed(stack))
        collapsed_dict[key] = collapsed_dict.get(key, 0) + current_sample_weight
        stack = []

if stack:
    key = ";".join(reversed(stack))
    collapsed_dict[key] = collapsed_dict.get(key, 0) + current_sample_weight

with open(out_path, 'w', encoding='utf-8') as out:
    for k, v in collapsed_dict.items():
        out.write(f"{k} {v}\n")
PY_PARSER_EOF

if [[ ! -s "$COLLAPSED_STACKS" ]]; then
    echo "Warning: No valid stack frames extracted. Writing minimal fallback SVG." >&2
    echo "all;idle 1" > "$COLLAPSED_STACKS"
fi

# Step 2: Render interactive, standards-compliant SVG flamegraph
python3 - << 'PY_RENDER_EOF' "$COLLAPSED_STACKS" "$OUTPUT_FILE" "$TITLE" "$COLOR_PALETTE" "$SVG_WIDTH"
import sys
import hashlib

in_path = sys.argv[1]
out_path = sys.argv[2]
title = sys.argv[3]
palette = sys.argv[4]
canvas_width = int(sys.argv[5])

# Build prefix tree of call stacks
class Node:
    def __init__(self, name):
        self.name = name
        self.value = 0
        self.children = {}

root = Node("root")
total_samples = 0

with open(in_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(' ', 1)
        if len(parts) != 2:
            continue
        stack_str, count_str = parts
        try:
            count = int(count_str)
        except ValueError:
            continue
        
        funcs = stack_str.split(';')
        curr = root
        curr.value += count
        for func in funcs:
            if not func:
                continue
            if func not in curr.children:
                curr.children[func] = Node(func)
            curr = curr.children[func]
            curr.value += count
        total_samples += count

if total_samples == 0:
    total_samples = 1

# Flatten tree into boxes: (name, depth, x_start_ratio, width_ratio, sample_count)
boxes = []

def traverse(node, depth, x_offset):
    curr_x = x_offset
    # Sort children by name for deterministic rendering
    for name, child in sorted(node.children.items()):
        child_width = child.value / total_samples
        boxes.append((name, depth, curr_x, child_width, child.value))
        traverse(child, depth + 1, curr_x)
        curr_x += child_width

traverse(root, 0, 0.0)

max_depth = max([b[1] for b in boxes], default=0) + 1
row_height = 18
header_height = 50
canvas_height = header_height + (max_depth * row_height) + 30

def get_color(name, pal):
    h = int(hashlib.md5(name.encode('utf-8')).hexdigest()[:6], 16)
    if pal == "io":
        # Cool blues / cyans for off-CPU / I/O
        r = 50 + (h % 60)
        g = 120 + ((h >> 4) % 80)
        b = 200 + ((h >> 8) % 55)
    elif pal == "mem":
        # Greens for heap / memory
        r = 50 + (h % 50)
        g = 160 + ((h >> 4) % 80)
        b = 60 + ((h >> 8) % 60)
    else:
        # Warm reds / yellows for on-CPU execution
        r = 200 + (h % 55)
        g = 50 + ((h >> 4) % 150)
        b = 50 + ((h >> 8) % 50)
    return f"rgb({r},{g},{b})"

svg_lines = []
svg_lines.append(f'<svg version="1.1" width="{canvas_width}" height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}" xmlns="http://www.w3.org/2000/svg">')
svg_lines.append('<style>')
svg_lines.append('  text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 11px; fill: #111; }')
svg_lines.append('  .func-box { stroke: #fff; stroke-width: 0.5px; cursor: pointer; transition: opacity 0.15s ease; }')
svg_lines.append('  .func-box:hover { opacity: 0.75; stroke: #000; stroke-width: 1px; }')
svg_lines.append('  #header-title { font-size: 18px; font-weight: bold; fill: #222; text-anchor: middle; }')
svg_lines.append('  #details { font-size: 12px; fill: #555; text-anchor: middle; }')
svg_lines.append('</style>')
svg_lines.append('<script type="text/ecmascript">')
svg_lines.append('<![CDATA[')
svg_lines.append('function showInfo(elem, name, samples, pct) {')
svg_lines.append('  var d = document.getElementById("details");')
svg_lines.append('  if (d) { d.textContent = "Function: " + name + " | Samples: " + samples + " (" + pct + "%)"; }')
svg_lines.append('}')
svg_lines.append('function resetInfo() {')
svg_lines.append('  var d = document.getElementById("details");')
svg_lines.append(f'  if (d) {{ d.textContent = "Total Samples: {total_samples} (Hover over frame to view details)"; }}')
svg_lines.append('}')
svg_lines.append(']]>')
svg_lines.append('</script>')

# Background
svg_lines.append(f'<rect width="100%" height="100%" fill="#f8f9fa" />')
svg_lines.append(f'<text id="header-title" x="{canvas_width / 2}" y="26">{title}</text>')
svg_lines.append(f'<text id="details" x="{canvas_width / 2}" y="44">Total Samples: {total_samples} (Hover over frame to view details)</text>')

left_margin = 10
right_margin = 10
usable_width = canvas_width - (left_margin + right_margin)

for name, depth, x_ratio, w_ratio, count in boxes:
    x = left_margin + (x_ratio * usable_width)
    w = max(w_ratio * usable_width, 1.0)
    # Flamegraphs grow upwards: depth 0 at bottom, max_depth at top
    y = canvas_height - 30 - ((depth + 1) * row_height)
    color = get_color(name, palette)
    pct = round((count / total_samples) * 100, 2)
    
    escaped_name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    
    svg_lines.append(
        f'<g onmouseover="showInfo(this, \'{escaped_name}\', {count}, {pct})" onmouseout="resetInfo()">'
        f'<rect class="func-box" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{row_height - 1}" fill="{color}" rx="2" ry="2"/>'
    )
    if w > 35:
        # Clip text if box is narrow
        display_text = escaped_name
        char_limit = int(w / 7)
        if len(display_text) > char_limit:
            display_text = display_text[:max(char_limit - 2, 1)] + '..'
        svg_lines.append(f'<text x="{x + 3:.2f}" y="{y + 12:.2f}">{display_text}</text>')
    svg_lines.append('</g>')

svg_lines.append('</svg>')

with open(out_path, 'w', encoding='utf-8') as out:
    out.write('\n'.join(svg_lines))

print(f"[+] Flamegraph SVG generated: {out_path} ({len(boxes)} frames rendered)")
PY_RENDER_EOF

