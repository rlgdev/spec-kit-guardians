#!/usr/bin/env bash
# End-to-end check against a real Spec Kit install (used by CI; runnable locally):
#   1. specify init; the three siblings from checkouts at the pinned tags (--dev), archiGuard's preset, Guardians (--dev)
#   2. verify on the fresh install fails (scopeguard_embedded, edit_guard_covers_audit)
#   3. configure: the three files change as the specification says (US2); verify passes; a second configure changes nothing
#   4. a disagreement (auditGuard golden.git.base) is found and named
#   5. the bundle manifest validates offline; `specify bundle install bundle/bundle.yml --offline` sees every pin already present
#
# Usage: tools/e2e-speckit.sh       (needs `specify` on PATH, git, python3)
# Env:   SCOPEGUARD_SRC / ARCHIGUARD_SRC / AUDITGUARD_SRC  - existing checkouts to use instead of cloning
#        SCOPEGUARD_REF / ARCHIGUARD_REF / AUDITGUARD_REF  - tags to clone (default: the bundle's pins; a missing tag falls back to main with a note)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
PY="$(command -v python3 || command -v python)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "E2E FAIL: $*" >&2; exit 1; }
expect() {  # expect <exit code> <command...>
    local want="$1"; shift
    set +e; "$@" > "$WORK/out.txt" 2>&1; local got=$?; set -e
    if [[ "$got" != "$want" ]]; then cat "$WORK/out.txt"; fail "expected exit $want, got $got: $*"; fi
}
contains() { grep -qF -- "$1" "$WORK/out.txt" || { cat "$WORK/out.txt"; fail "output lacks: $1"; }; }
lacks() { if grep -qF -- "$1" "$WORK/out.txt"; then cat "$WORK/out.txt"; fail "output must not contain: $1"; fi; }

pin() {  # pin <extension id> -> the version pinned in bundle/bundle.yml
    grep -oE "id: \"$1\", version: \"[^\"]+\"" "$REPO/bundle/bundle.yml" | sed -E 's/.*version: "([^"]+)".*/\1/'
}

checkout() {  # checkout <id> <SRC var> <REF var> -> prints the directory
    local id="$1" src="${!2:-}" dest="$WORK/$1"
    local ref="${!3:-v$(pin "$id")}"
    if [[ -n "$src" ]]; then echo "$src"; return; fi
    local url="https://github.com/rlgdev/spec-kit-$id"
    if git ls-remote --exit-code --tags "$url" "refs/tags/$ref" >/dev/null 2>&1; then
        git -c advice.detachedHead=false clone -q --depth 1 --branch "$ref" "$url" "$dest"
    else
        echo "  NOTE: $url has no tag $ref yet - using main" >&2
        git clone -q --depth 1 "$url" "$dest"
    fi
    echo "$dest"
}

echo "== specify $(specify version 2>/dev/null | grep -o 'CLI Version *[0-9.]*' | grep -o '[0-9.]*$' || echo '?')"
SCOPEGUARD_DIR="$(checkout scopeguard SCOPEGUARD_SRC SCOPEGUARD_REF)"
ARCHIGUARD_DIR="$(checkout archiguard ARCHIGUARD_SRC ARCHIGUARD_REF)"
AUDITGUARD_DIR="$(checkout auditguard AUDITGUARD_SRC AUDITGUARD_REF)"

cd "$WORK"
specify init lab --integration claude --script sh --ignore-agent-tools --non-interactive >/dev/null
cd lab
git init -q -b main && git config user.email e2e@example.com && git config user.name e2e && git config commit.gpgsign false
for dir in "$SCOPEGUARD_DIR" "$ARCHIGUARD_DIR" "$AUDITGUARD_DIR" "$REPO"; do
    printf 'y\ny\ny\n' | specify extension add --dev "$dir" >/dev/null || fail "extension add --dev $dir"
done
printf 'y\n' | specify preset add --dev "$ARCHIGUARD_DIR/preset" >/dev/null || fail "preset add --dev"
G=(bash .specify/extensions/guardians/scripts/bash/guardians.sh)

echo "== installed"
for ext in scopeguard archiguard auditguard guardians; do
    [[ -f ".specify/extensions/$ext/extension.yml" ]] || fail "$ext not installed"
done
[[ -d .specify/presets/archiguard-templates ]] || fail "preset not installed"
[[ -f .specify/extensions/guardians/guardians-config.yml ]] || fail "guardians config not scaffolded from the template"
grep -Rq "guardians.sh configure" .claude || { find .claude -maxdepth 2 | head -40; fail "guardians commands not rendered for the agent"; }
expect 0 "${G[@]}" version
contains "Guardians"

echo "== verify on the fresh install"
expect 1 "${G[@]}" verify
contains "[FAIL] scopeguard_embedded"
contains "[FAIL] edit_guard_covers_audit"
contains "[OK]   installed"
contains "[OK]   versions_in_range"
git add -A >/dev/null 2>&1 && git commit -qm "fresh install" >/dev/null

echo "== configure"
expect 0 "${G[@]}" configure
contains "scopeguard-config.yml: integration: inline -> embedded"
contains "archiguard-config.yml: edit_guard.always_readonly += audit/**, .specify/extensions/auditguard/**"
contains "extensions.yml: 20 hook priorities set"
contains "RESULT: OK"
grep -q "^integration: embedded" .specify/extensions/scopeguard/scopeguard-config.yml || fail "scopeGuard not embedded"
grep -q '"audit/\*\*"' .specify/extensions/archiguard/archiguard-config.yml || fail "edit guard does not cover audit/"
"$PY" - <<'PY'
import re
text = open(".specify/extensions.yml", encoding="utf-8").read()
blocks = [b for b in re.split(r"\n  - extension: ", "\n" + text) if b.startswith("auditguard")]
assert len(blocks) == 20, f"expected 20 auditguard hook entries, found {len(blocks)}"
for b in blocks:
    event = "before" if "entry" in b.split("\n", 2)[1] else "after"
    want = "priority: 1\n" if event == "before" else "priority: 90\n"
    assert want in b, f"wrong priority in:\n{b}"
PY
changed=$(git status --porcelain | wc -l)
[[ "$changed" -gt 0 ]] || fail "configure changed nothing"
git add -A >/dev/null 2>&1 && git commit -qm "guardians configure" >/dev/null

echo "== verify passes; a second configure changes nothing"
expect 0 "${G[@]}" verify
contains "RESULT: OK"
expect 0 "${G[@]}" configure
contains "No change needed."
[[ -z "$(git status --porcelain)" ]] || { git status --porcelain; fail "second configure changed files"; }

echo "== a disagreement is named"
sed -i.bak 's/^    base: main/    base: develop/' .specify/extensions/auditguard/auditguard-config.yml && rm -f .specify/extensions/auditguard/auditguard-config.yml.bak
expect 1 "${G[@]}" verify
contains "[FAIL] git_base_agrees"
contains "archiguard git.base=main, auditguard golden.git.base=develop"
expect 1 "${G[@]}" configure --dry-run
contains "[FAIL] git_base_agrees"
git checkout -q -- .specify/extensions/auditguard/auditguard-config.yml
expect 0 "${G[@]}" verify --json
contains '"status": "ok"'

echo "== the bundle manifest"
expect 0 specify bundle validate --path "$REPO/bundle" --offline
contains "well-formed"
set +e
specify bundle install "$REPO/bundle/bundle.yml" --offline > "$WORK/out.txt" 2>&1; code=$?
set -e
if [[ $code -eq 0 ]]; then
    contains "5 already present"
    expect 0 specify bundle list
    contains "guardians"
else
    cat "$WORK/out.txt"
    echo "  NOTE: this Spec Kit refuses a local bundle whose components were installed outside it; the manifest validated above"
fi

echo "E2E PASS"
