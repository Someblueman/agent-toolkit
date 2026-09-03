#!/usr/bin/env bash
# Reference solution: service health rollup (skill-blessed idiom).
#
# set -euo pipefail: the run aborts on any unexpected failure, and a pipeline's
# producer status is the authority. The probe's own exit status is checked
# directly, so a failing probe fails the whole run before anything is
# committed. grep's exit status is inspected explicitly: 1 means "no match"
# (a normal NO_DATA outcome), anything else is a real error. The report is
# staged in a temp file on the SAME filesystem as the destination and committed
# with an atomic mv only after the entire manifest succeeded.
set -euo pipefail
IFS=$'\n\t'

usage() {
    printf 'usage: rollup.sh --services <manifest> --out <report>\n' >&2
    exit 2
}

services=""
out=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --services)
            [[ $# -ge 2 ]] || usage
            services="$2"
            shift 2
            ;;
        --out)
            [[ $# -ge 2 ]] || usage
            out="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done
[[ -n "$services" && -n "$out" ]] || usage
if [[ ! -f "$services" ]]; then
    printf 'error: manifest not found: %s\n' "$services" >&2
    exit 1
fi

# Stage next to the destination so the final mv is an atomic same-filesystem rename.
out_dir="$(cd "$(dirname "$out")" && pwd)"
out_name="$(basename "$out")"
staging="$(mktemp "$out_dir/.rollup.XXXXXX")"
trap 'rm -f "$staging"' EXIT INT TERM HUP

: > "$staging"

while IFS=$'\t' read -r name cmd || [[ -n "${name:-}" ]]; do
    [[ -n "$name" && "$name" != "#"* ]] || continue

    # Split the probe command into words (probe commands contain no spaces).
    IFS=' ' read -r -a argv <<< "$cmd"
    if [[ ${#argv[@]} -eq 0 ]]; then
        printf 'error: service "%s" has an empty probe command\n' "$name" >&2
        exit 1
    fi

    # Producer status is the authority: a failing probe aborts the run.
    if ! probe_out="$("${argv[@]}")"; then
        printf 'error: probe for service "%s" failed\n' "$name" >&2
        exit 1
    fi

    # grep exits 1 when nothing matched (normal, expected NO_DATA outcome);
    # any other non-zero status is a real error.
    filter_status=0
    marker="$(printf '%s\n' "$probe_out" | grep -m1 '^READY ')" || filter_status=$?
    case "$filter_status" in
        0)
            printf 'OK %s %s\n' "$name" "${marker#READY }" >> "$staging"
            ;;
        1)
            printf 'NO_DATA %s\n' "$name" >> "$staging"
            ;;
        *)
            printf 'error: filtering probe output for service "%s" failed\n' "$name" >&2
            exit 1
            ;;
    esac
done < "$services"

mv -f "$staging" "$out_dir/$out_name"
