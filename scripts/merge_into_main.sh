#!/usr/bin/env bash
# Merges a worktree branch into main in the main checkout. Never pushes.
#
# With no branch named, it looks for worktrees whose branch has commits
# that main does not, and offers them. It fast-forwards when main has not
# moved, and otherwise makes a merge commit with git's default message.
# It refuses to start if the main checkout is not on main, has uncommitted
# changes to tracked files, or is mid-merge, and it warns when the worktree
# being merged has uncommitted changes (they are not part of the merge).
#
# Usage: ./scripts/merge_into_main.sh [BRANCH] [--test] [--clean] [--yes]
#   --test   run ./scripts/test-suite.sh after the merge
#   --clean  remove the merged worktree and delete its branch
#   --yes    do not ask for confirmation
set -euo pipefail

usage() { sed -n '/^# Usage:/,/^#   --yes/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"; }
fail() { echo "error: $*" >&2; exit 1; }

BRANCH=""
RUN_TESTS=0
CLEAN=0
ASSUME_YES=0

for arg in "$@"; do
    case "$arg" in
        --test) RUN_TESTS=1 ;;
        --clean) CLEAN=1 ;;
        --yes) ASSUME_YES=1 ;;
        -h | --help) usage; exit 0 ;;
        -*) usage >&2; fail "unknown option: $arg" ;;
        *) [[ -z "$BRANCH" ]] || fail "only one branch at a time"; BRANCH="$arg" ;;
    esac
done

# The main checkout is the parent of the shared .git directory, so this
# works when run from a worktree too.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="$(git -C "$SCRIPT_DIR" rev-parse --path-format=absolute --git-common-dir)"
MAIN_CHECKOUT="$(dirname -- "$COMMON_DIR")"
cd "$MAIN_CHECKOUT"

[[ "$(git branch --show-current)" == "main" ]] || fail "$MAIN_CHECKOUT is not on main"
git rev-parse -q --verify MERGE_HEAD > /dev/null && fail "a merge is in progress; finish it (git commit) or abort it (git merge --abort)"
git diff --quiet HEAD || fail "the main checkout has uncommitted changes to tracked files; commit or stash them first"

# Worktree paths and branches, skipping the main checkout.
declare -A PATH_OF=()
CANDIDATES=()
worktree_path=""
while IFS= read -r line; do
    case "$line" in
        "worktree "*) worktree_path="${line#worktree }" ;;
        "branch refs/heads/"*)
            name="${line#branch refs/heads/}"
            [[ "$worktree_path" == "$MAIN_CHECKOUT" ]] && continue
            PATH_OF["$name"]="$worktree_path"
            if [[ "$(git rev-list --count "main..refs/heads/$name")" -gt 0 ]]; then
                CANDIDATES+=("$name")
            fi
            ;;
    esac
done < <(git worktree list --porcelain)

if [[ -z "$BRANCH" ]]; then
    case "${#CANDIDATES[@]}" in
        0) echo "Nothing to merge: every worktree branch is already in main."; exit 0 ;;
        1) BRANCH="${CANDIDATES[0]}" ;;
        *)
            echo "Worktree branches not yet in main:"
            for i in "${!CANDIDATES[@]}"; do
                printf '  %d) %s (%s commits)\n' "$((i + 1))" "${CANDIDATES[$i]}" \
                    "$(git rev-list --count "main..refs/heads/${CANDIDATES[$i]}")"
            done
            read -rp "Merge which? [1-${#CANDIDATES[@]}] " choice
            [[ "$choice" =~ ^[0-9]+$ ]] && ((choice >= 1 && choice <= ${#CANDIDATES[@]})) || fail "no branch chosen"
            BRANCH="${CANDIDATES[$((choice - 1))]}"
            ;;
    esac
fi

REF="refs/heads/$BRANCH"
git rev-parse -q --verify "$REF" > /dev/null || fail "no local branch named $BRANCH"
[[ "$(git rev-list --count "main..$REF")" -gt 0 ]] || { echo "$BRANCH is already in main."; exit 0; }

WORKTREE="${PATH_OF[$BRANCH]:-}"
if [[ -n "$WORKTREE" && -n "$(git -C "$WORKTREE" status --porcelain --untracked-files=no)" ]]; then
    echo "warning: $WORKTREE has uncommitted changes; they will not be merged." >&2
fi

echo "Merging $BRANCH into main:"
git log --oneline "main..$REF"
git diff --stat "main...$REF" | tail -1

if ((!ASSUME_YES)); then
    read -rp "Proceed? [y/N] " answer
    [[ "$answer" == [yY]* ]] || { echo "Cancelled."; exit 0; }
fi

if git merge-base --is-ancestor main "$REF"; then
    git merge --ff-only "$REF"
elif ! git merge --no-ff -m "Merge branch '$BRANCH'" "$REF"; then
    echo >&2
    fail "the merge stopped on conflicts; resolve them and run git commit, or undo it with git merge --abort"
fi

if ((RUN_TESTS)); then
    "$MAIN_CHECKOUT/scripts/test-suite.sh" || fail "the test suite failed on the merged main; nothing was pushed"
fi

if ((CLEAN)) && [[ -n "$WORKTREE" ]]; then
    git worktree remove "$WORKTREE"
    git branch -d "$BRANCH"
fi

echo
echo "Merged $BRANCH into main. Nothing was pushed; when ready: git push"
