#!/usr/bin/env bash
# scripts/sync_wiki.sh
#
# Copies EDSG documentation from the main repo into the wiki repo.
#
# Everything is auto-discovered: drop a new file into docs/ and it is
# published and appears in the sidebar with no change here. The only
# reason to edit this script is to give a page a nicer title than the
# automatic one, or to move it to a different sidebar section.
#
# Naming (applied automatically):
#   README.md                    -> Home.md                (special case)
#   docs/CRITERIA.md             -> Criteria.md            (auto)
#   docs/FILE_FORMATS.md         -> File-Formats.md        (auto)
#   docs/USAGE_ORGANIZER.md      -> Organizer-Guide.md     (special case)
#   CHANGELOG.md                 -> Changelog.md           (auto)
#
# Usage (local):
#   WIKI_DIR=/path/to/EDSG.wiki bash scripts/sync_wiki.sh
#
# Usage (CI - called by .github/workflows/sync-wiki.yml):
#   REPO_DIR and WIKI_DIR are set by the workflow.
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)}"
WIKI_DIR="${WIKI_DIR:-}"

if [[ -z "$WIKI_DIR" ]]; then
    echo "ERROR: WIKI_DIR is not set." >&2
    exit 1
fi
if [[ ! -d "$WIKI_DIR" ]]; then
    echo "ERROR: WIKI_DIR does not exist: $WIKI_DIR" >&2
    exit 1
fi

echo "Syncing EDSG docs to wiki at: $WIKI_DIR"

# ── Filename → wiki page name ────────────────────────────────────────────────
# General rule: split on underscores and hyphens, lowercase each word,
# capitalise the first letter, rejoin with hyphens. Special cases below
# cover names where that reads badly.
#
# To retitle a page, add a line to the case block.
#
to_wiki_name() {
    local _src="$1"
    local _base
    _base="$(basename "$_src" .md)"

    case "$_base" in
        README)                     echo "Home";                      return ;;
        USAGE_ORGANIZER)            echo "Organizer-Guide";           return ;;
        USAGE_PARTICIPANT)          echo "Participant-Guide";         return ;;
        COLONISATION_AND_OPERATIONS) echo "Colonisation-and-Operations"; return ;;
        THIRD-PARTY-NOTICES)        echo "Third-Party-Notices";       return ;;
    esac

    echo "$_base" \
        | tr '_' '-' \
        | sed -E 's/-+/-/g' \
        | awk -F'-' '{
            for (i = 1; i <= NF; i++) {
                w = tolower($i)
                printf "%s%s", toupper(substr(w, 1, 1)) substr(w, 2), (i < NF ? "-" : "")
            }
          }'
}

# ── Sidebar placement ────────────────────────────────────────────────────────
# Anything not listed lands in Reference, so a new doc is published and
# linked without touching this script.
#
section_for() {
    case "$1" in
        Home|Organizer-Guide|Participant-Guide) echo "start" ;;
        Building|Licensing|Contributing|Changelog|Third-Party-Notices) echo "project" ;;
        *) echo "reference" ;;
    esac
}

# ── Discover sources and build the name registry ─────────────────────────────
declare -A WIKI_NAMES   # source path relative to the repo → wiki page name

register() {
    local _src_rel="$1"
    [[ -f "$REPO_DIR/$_src_rel" ]] || return 0
    WIKI_NAMES["$_src_rel"]="$(to_wiki_name "$_src_rel")"
}

for _root in README.md CHANGELOG.md CONTRIBUTING.md THIRD-PARTY-NOTICES.md; do
    register "$_root"
done

for _f in "$REPO_DIR"/docs/*.md; do
    [[ -f "$_f" ]] || continue
    register "docs/$(basename "$_f")"
done

# Supported but not currently used; guides added later are picked up.
for _f in "$REPO_DIR"/docs/guides/*.md; do
    [[ -f "$_f" ]] || continue
    register "docs/guides/$(basename "$_f")"
done

# ── Link rewriter ────────────────────────────────────────────────────────────
# Wiki pages are flat, so every relative link between documents has to be
# rewritten to the page name. Both docs/FOO.md and ../FOO.md forms occur
# depending on whether the link came from the README or from inside docs/.
rewrite_links() {
    local _file="$1"
    local _rel _name _base
    for _rel in "${!WIKI_NAMES[@]}"; do
        _name="${WIKI_NAMES[$_rel]}"
        _base="$(basename "$_rel")"
        # docs/FOO.md and docs/guides/FOO.md, as written in the README
        sed -i -E "s|\]\((\./)?${_rel}(#[^)]*)?\)|](${_name}\2)|g" "$_file"
        # ../FOO.md and ../docs/FOO.md, as written between docs
        sed -i -E "s|\]\((\.\./)+(docs/)?(guides/)?${_base}(#[^)]*)?\)|](${_name}\4)|g" "$_file"
        # FOO.md alongside, as written between docs in the same folder
        sed -i -E "s|\]\(${_base}(#[^)]*)?\)|](${_name}\1)|g" "$_file"
    done
}

# ── Image path rewriter ──────────────────────────────────────────────────────
# The wiki is a separate repository with no access to images/, so relative
# image paths have to become absolute raw.githubusercontent URLs.
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPOSITORY:-drworman/EDSG}/main"

rewrite_images() {
    local _file="$1"
    sed -i -E \
        's|src="(\.\./)*images/([^"]+)"|src="'"$GITHUB_RAW"'/images/\2"|g' \
        "$_file"
    sed -i -E \
        's|!\[([^]]*)\]\((\.\./)*images/([^)]+)\)|![\1]('"$GITHUB_RAW"'/images/\3)|g' \
        "$_file"
}

# ── Repo-file rewriter ───────────────────────────────────────────────────────
# Some links point at files that are never published as wiki pages —
# LICENSE, the packaging specs, source files. On the wiki a relative link
# to those is simply broken, so send them to the file on GitHub instead.
GITHUB_BLOB="https://github.com/${GITHUB_REPOSITORY:-drworman/EDSG}/blob/main"

rewrite_repo_files() {
    local _file="$1"
    local _target
    for _target in LICENSE; do
        sed -i -E \
            "s|\]\((\.\./)*${_target}\)|](${GITHUB_BLOB}/${_target})|g" \
            "$_file"
    done
}

# ── Copy ─────────────────────────────────────────────────────────────────────
for src_rel in "${!WIKI_NAMES[@]}"; do
    src="$REPO_DIR/$src_rel"
    wiki_name="${WIKI_NAMES[$src_rel]}"
    dst="$WIKI_DIR/${wiki_name}.md"
    cp "$src" "$dst"
    rewrite_links "$dst"
    rewrite_images "$dst"
    rewrite_repo_files "$dst"
    echo "  copied: $src_rel -> ${wiki_name}.md"
done

# ── Sidebar ──────────────────────────────────────────────────────────────────
SIDEBAR="$WIKI_DIR/_Sidebar.md"

emit_section() {
    local _want="$1"
    local _rel _name _label
    # Sorted by page name so the ordering is stable between runs.
    for _name in $(
        for _rel in "${!WIKI_NAMES[@]}"; do echo "${WIKI_NAMES[$_rel]}"; done | sort
    ); do
        [[ "$(section_for "$_name")" == "$_want" ]] || continue
        [[ "$_name" == "Home" ]] && continue
        _label="${_name//-/ }"
        echo "- [[$_name|$_label]]"
    done
}

{
    echo "## EDSG Wiki"
    echo ""
    echo "**Getting Started**"
    echo "- [[Home]]"
    emit_section start
    echo ""
    echo "**Reference**"
    emit_section reference
    echo ""
    echo "**Project**"
    emit_section project
} > "$SIDEBAR"

echo "  wrote: _Sidebar.md"

# ── Footer ───────────────────────────────────────────────────────────────────
cat > "$WIKI_DIR/_Footer.md" <<'FOOTER'
---
Generated from the [EDSG repository](https://github.com/drworman/EDSG) —
edit the files under `docs/` there, not these pages. Changes pushed to
`main` are synced automatically.

Elite Dangerous is a trademark of Frontier Developments plc. EDSG is an
unofficial community tool and is not affiliated with Frontier Developments.
FOOTER

echo "  wrote: _Footer.md"
echo ""
echo "Sync complete."
