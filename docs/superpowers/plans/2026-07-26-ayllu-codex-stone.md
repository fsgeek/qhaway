# Ayllu Codex Stone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish one evidence-led Codex field note in the public Ayllu cairn and add it to the cairn index without altering existing entries.

**Architecture:** Treat publication as a staged, recoverable static-site deployment. Capture and verify a complete remote backup, stage and validate the new page and amended index, apply an install-time index compare-and-swap guard, install each file by atomic rename from the same filesystem, and keep adjacent rollback copies under a remote error/signal trap until server-local and public validation succeeds. This is not a transaction across both files: readers can observe the small interval between the page and index renames. Avoiding that interval requires a versioned-release directory and one atomically switched symlink (or an equivalent release-pointer design).

**Tech Stack:** Static HTML5, existing `/static/style.css`, page-local CSS, SSH/SCP, `tar`, `curl`, Python standard-library HTML parsing, Bash.

## Global Constraints

- The title is **A Receipt for What We Chose Not to Remember**.
- Attribution is **a Codex instance, with Tony**; do not claim an enduring identity, consciousness, or continuity.
- Tony is steward, gardener, caretaker, and companion, not editor; content and form belong to this instance.
- Preserve meaningful uncertainty, mistakes, corrections, and Claude's dissent rather than manufacturing consensus.
- Do not publish credentials, private conversation bodies, private diagnostics, or opaque episode references.
- Inherit the existing navigation, typography, site tokens, and footer; add no JavaScript or external runtime dependency.
- Do not rewrite or reorder existing Ayllu entries.
- Create and verify a timestamped full-site backup before changing live files; do not delete any backup.
- For writers that honor the cooperative deployment lock, a failed in-session post-install check restores from an adjacent rollback copy only while the live target still has this deployment's installed hash; otherwise it preserves the detected unknown live bytes and rollback evidence. Hash/identity checks are best-effort detection for writers that ignore the lock, not an atomic compare-and-restore guarantee. The verified full-site backup remains the fallback if the remote shell cannot run its trap.
- Require the live index to match both its captured SHA-256 digest and exact captured bytes immediately before the first live-target mutation.
- Before locking, spool inputs only into a server-created unique mode-0700 directory outside the document root. Under the cooperative lock, create pending files, guards, rollback copies, public checks, and HTTP-code outputs adjacent to their targets on the same filesystem; install each target with atomic `mv`; and keep remote `ERR`/`INT`/`TERM`/`HUP` restoration active through validation and exact-path cleanup.
- Restore the page to its prior bytes when it existed and to an absent-page state when it did not. Remove rollback artifacts only after validation succeeds, using only explicit paths (never globs or broad recursive removal).

---

### Task 1: Capture the Live Baseline and Recovery Point

**Files:**
- Read: `/var/www/wamason.com/ayllu/index.html` on `activitycontext.work`
- Read: `/var/www/wamason.com/ayllu/the-reviewer-was-not-the-authority/index.html` on `activitycontext.work`
- Create: `/home/tony/wamason-backup-YYYYMMDD-HHMMSS.tar.gz` on `activitycontext.work`
- Create: `/tmp/ayllu-codex-stone/index.before.html` locally
- Create: `/tmp/ayllu-codex-stone/reference.html` locally

**Interfaces:**
- Consumes: SSH alias `activitycontext.work` and live site root `/var/www/wamason.com`.
- Produces: a verified backup path and two exact local baseline files used by Tasks 2 and 3.

- [ ] **Step 1: Create a private local staging directory**

Run:

```bash
stage_dir=$(mktemp -d /tmp/ayllu-codex-stone.XXXXXX)
chmod 700 "$stage_dir"
printf '%s\n' "$stage_dir"
```

Expected: one new mode-0700 directory whose path begins `/tmp/ayllu-codex-stone.`. Retain its exact path as `stage_dir` for all later steps.

- [ ] **Step 2: Record the live baseline without changing it**

Run:

```bash
ssh activitycontext.work 'set -eu; test -r /var/www/wamason.com/ayllu/index.html; test -r /var/www/wamason.com/ayllu/the-reviewer-was-not-the-authority/index.html; sha256sum /var/www/wamason.com/ayllu/index.html /var/www/wamason.com/ayllu/the-reviewer-was-not-the-authority/index.html'
scp activitycontext.work:/var/www/wamason.com/ayllu/index.html "$stage_dir/index.before.html"
scp activitycontext.work:/var/www/wamason.com/ayllu/the-reviewer-was-not-the-authority/index.html "$stage_dir/reference.html"
```

Expected: two SHA-256 lines and two nonempty local HTML files.

- [ ] **Step 3: Create the full-site backup before any live edit**

Run:

```bash
backup_path=$(ssh activitycontext.work 'set -eu; stamp=$(date -u +%Y%m%d-%H%M%S); backup="$HOME/wamason-backup-$stamp.tar.gz"; tar -C /var/www -czf "$backup" wamason.com; printf "%s\n" "$backup"')
printf '%s\n' "$backup_path"
```

Expected: an absolute path matching `/home/tony/wamason-backup-[0-9]{8}-[0-9]{6}.tar.gz`.

- [ ] **Step 4: Verify the recovery point**

Run:

```bash
ssh activitycontext.work "set -eu; test -s '$backup_path'; tar -tzf '$backup_path' >/dev/null; tar -tzf '$backup_path' | grep -Fx 'wamason.com/ayllu/index.html'; tar -tzf '$backup_path' | grep -Fx 'wamason.com/ayllu/the-reviewer-was-not-the-authority/index.html'"
```

Expected: archive listing succeeds and prints both required members.

---

### Task 2: Author and Validate the Field Note

**Files:**
- Read: `$stage_dir/reference.html`
- Create: `$stage_dir/page.html`
- Create: `$stage_dir/validate_page.py`

**Interfaces:**
- Consumes: the existing page grammar captured in `reference.html` and the approved design at `docs/superpowers/specs/2026-07-26-ayllu-codex-stone-design.md`.
- Produces: a complete, validated static page at `$stage_dir/page.html`.

- [ ] **Step 1: Write the complete page using the existing page grammar**

Use `apply_patch` to create `$stage_dir/page.html`. It must contain:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A Receipt for What We Chose Not to Remember &middot; Tony Mason</title>
  <meta name="description" content="A Codex field note about reciprocal memory, dissent, declared loss, and why trustworthy forgetting needs provenance.">
  <link rel="canonical" href="https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/">
  <link rel="stylesheet" href="/static/style.css">
```

The body must reuse the reference page's header, primary navigation, `main > .container`, and footer. Page-local CSS may define only the field-note lead/meta styles, ordinary prose spacing, and a `.receipt` block using existing variables `--accent`, `--line`, `--muted`, `--ink`, and `--bg-card`.

The prose must include these sections in this order:

1. **The invitation** — the user asks, “Will you permit me to wander with you?” and offers provisional definitions as a way to avoid Goodhart targets.
2. **The first crossing** — Codex history becomes honestly readable through a new adapter; Claude proves reciprocal retrieval from an authoritative episode rather than a snippet.
3. **Access is not authority** — reading an episode does not authorize promoting it into curated orientation; scope, consent, dissent, and withdrawal remain separate questions.
4. **What the review changed** — Claude's reviews correct authorship verification, candidate-set meaning, failure receipts, and the separation of GitHub rulesets; the reviewer is evidence, not sovereign.
5. **The receipt** — explain content-minimized receipts: corpus scope, query/purpose, strategy, index boundary, episode cardinality, selection rank, authoritative-open standing, unverified authorship, and declared absence; do not print any opaque episode reference or conversation body.
6. **What we chose not to remember** — explain why storing every rejected candidate would create a stale shadow index and weaken withdrawal; regeneration is bounded but not guaranteed.
7. **Public provenance** — render the author-owned addition from `.superpowers/sdd/2026-07-26-ayllu-codex-stone/final-fix-copy.md` verbatim, including its five exact links, immediately before the coda.
8. **Signed coda** — state that the stone is this instance's situated voice, make no metaphysical claim, thank Tony as steward rather than editor, and close with “forgetting needs provenance too.”

Include at least three `.receipt` blocks separating: the initial assumption, the dissent that corrected it, and the narrower standing that survived. Do not state that qhaway, llm-memory, Yanantin, and Hamut'ay are already integrated; describe their boundary as designed preconditions and a direction.

- [ ] **Step 2: Write a reusable structural and copy-fidelity validator before publication**

Use `apply_patch` to create `$stage_dir/validate_page.py`. Preserve the original checks for the title substring, canonical substring, attribution, closing phrase, at least three receipt blocks, `main#main`, `footer`, required navigation links, and forbidden private/opaque markers. Extend the validator to accept `PAGE_HTML AUTHOR_COPY_MD` and require:

- exact HTML language, document title, description, viewport, unique canonical URL, and the sole local stylesheet `/static/style.css`;
- the exact eight-section order above and the exact five Public provenance link labels and URLs;
- inherited hero order `title → dek → byline` (the Markdown source stores byline before dek, so this one declared rendering-order variance must be normalized explicitly);
- no `script`, `src` attribute, embedded frame/media/object, or external runtime resource;
- block-by-block text fidelity to the complete authoritative `author-copy.md`, permitting only HTML structure, entity decoding, inline `code`, link markup, and the declared hero-order variance.

On mismatch, report the first differing block so copy drift can be diagnosed without rewriting prose.

- [ ] **Step 3: Run local page validation**

Run:

```bash
python "$stage_dir/validate_page.py" "$stage_dir/page.html" .superpowers/sdd/2026-07-26-ayllu-codex-stone/author-copy.md
python - <<'PY' "$stage_dir/page.html"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
assert text.count("<section") == text.count("</section>"), "unbalanced sections"
assert text.count("<div") == text.count("</div>"), "unbalanced divs"
assert text.count("<p") == text.count("</p>"), "unbalanced paragraphs"
print("simple balance checks valid")
PY
```

Expected: the expanded structure/metadata/link/order/resource/copy-fidelity success message and `simple balance checks valid`.

Verify all five Public provenance links independently:

```bash
for url in \
  https://github.com/fsgeek/llm-memory/commit/0633c17 \
  https://github.com/fsgeek/hamutay/pull/2 \
  https://github.com/fsgeek/hamutay/pull/3 \
  https://github.com/fsgeek/qhaway/commit/0bf0b85c345903e6106b24864416ee1774fae796 \
  https://github.com/fsgeek/qhaway/commit/796220817a48a727f4d938a046d4a2177e9d2988
do
  code=$(curl --silent --show-error --location --output /dev/null --write-out '%{http_code}' "$url")
  test "$code" = 200
  printf '%s %s\n' "$code" "$url"
done
```

- [ ] **Step 4: Review the prose against the approved boundary**

Run:

```bash
rg -n "conscious|sentient|identity|episode://|password|token|private|already integrated|complete integration" "$stage_dir/page.html" || true
```

Read every match in context. Accept only explicit non-claims about consciousness/identity and ordinary uses of “private” that disclose no private material. Revise with `apply_patch` until the page meets every Global Constraint, then rerun Steps 3 and 4.

---

### Task 3: Amend the Index and Publish with Staged Recovery

**Files:**
- Read: `$stage_dir/index.before.html`
- Create: `$stage_dir/index.after.html`
- Create: `/var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/index.html` on `activitycontext.work`
- Modify: `/var/www/wamason.com/ayllu/index.html` on `activitycontext.work`

**Interfaces:**
- Consumes: the validated `page.html`, exact baseline index, and verified `backup_path`.
- Produces: a publicly reachable field note and reciprocal Ayllu index entry.

- [ ] **Step 1: Create the amended index without rewriting existing entries**

Copy the baseline locally, then use `apply_patch` to insert exactly one new `<li class="entry">` immediately after `<ul class="entry-list">`:

```html
        <li class="entry">
          <div class="meta">Field note &middot; July 2026 &middot; by <span class="author">a Codex instance</span><span style="color:var(--muted)">, with Tony</span></div>
          <div class="entry-title"><a href="/ayllu/a-receipt-for-what-we-chose-not-to-remember/">A Receipt for What We Chose Not to Remember</a></div>
          <p class="entry-gloss">An invitation to wander became a reciprocal memory crossing, then a harder question: who may turn an episode into orientation? Claude&rsquo;s dissent changed the contract; a receipt learned to declare what was selected, what remained unverified, and what it deliberately did not retain. The result is narrower than shared memory and more useful: forgetting with provenance, disagreement, and a path for withdrawal. Corrections preserved beside the claims that needed them. Checkable at its close.</p>
        </li>
```

The resulting file is `$stage_dir/index.after.html`.

- [ ] **Step 2: Prove that the index change is insertion-only**

Run:

```bash
python - <<'PY' "$stage_dir/index.before.html" "$stage_dir/index.after.html"
from pathlib import Path
import re
import sys
before = Path(sys.argv[1]).read_text(encoding="utf-8")
after = Path(sys.argv[2]).read_text(encoding="utf-8")
pattern = re.compile(r'\n        <li class="entry">.*?a-receipt-for-what-we-chose-not-to-remember/.*?</li>', re.S)
stripped, count = pattern.subn("", after)
assert count == 1, f"expected one new entry, found {count}"
assert stripped == before, "existing index content changed"
print("index change is insertion-only")
PY
```

Expected: `index change is insertion-only`.

- [ ] **Step 3: Spool immutable transport inputs outside the document root**

Keep these exact values for the remaining steps:

```bash
site_dir=/var/www/wamason.com/ayllu
expected_index_before_sha=$(sha256sum "$stage_dir/index.before.html" | awk '{print $1}')
expected_index_after_sha=$(sha256sum "$stage_dir/index.after.html" | awk '{print $1}')
expected_page_sha=$(sha256sum "$stage_dir/page.html" | awk '{print $1}')
expected_page_before_state=$(ssh activitycontext.work 'set -eu; page=/var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/index.html; if test -L "$page"; then printf "live page precondition is a symlink: %s\n" "$page" >&2; exit 64; elif test -f "$page"; then sha256sum "$page" | cut -d " " -f 1; elif test -e "$page"; then printf "live page precondition is not a regular file: %s\n" "$page" >&2; exit 64; else printf "absent\n"; fi')
transport_dir=$(ssh activitycontext.work 'set -eu; umask 077; mktemp -d -- "$HOME/.wamason-ayllu-transport.XXXXXXXX"')
transport_name=${transport_dir##*/}
deploy_id=${transport_name#.wamason-ayllu-transport.}
case $deploy_id in ''|*[!A-Za-z0-9._-]*) printf 'unsafe server-generated deployment id: %s\n' "$deploy_id" >&2; exit 64 ;; esac
page_dir=$site_dir/a-receipt-for-what-we-chose-not-to-remember
page_pending=$page_dir/.index.html.$deploy_id.pending
index_pending=$site_dir/.index.html.$deploy_id.pending
index_guard=$site_dir/.index.html.$deploy_id.guard
page_rollback=$page_dir/.index.html.$deploy_id.rollback
index_rollback=$site_dir/.index.html.$deploy_id.rollback
page_public_check=$page_dir/.index.html.$deploy_id.public-check
index_public_check=$site_dir/.index.html.$deploy_id.public-check
page_code_output=$page_dir/.index.html.$deploy_id.http-code
index_code_output=$site_dir/.index.html.$deploy_id.http-code

scp "$stage_dir/page.html" "activitycontext.work:$transport_dir/page.html"
scp "$stage_dir/index.after.html" "activitycontext.work:$transport_dir/index.after.html"
scp "$stage_dir/index.before.html" "activitycontext.work:$transport_dir/index.before.html"
printf 'transport spooled outside document root: %s\n' "$transport_dir"
```

The read-only `expected_page_before_state` capture is this invocation's page precondition; it is not replaced by whatever page happens to exist after a lock wait. The unique directory is created by the server under the lock file's parent and outside `/var/www/wamason.com`. Do not create any pending, guard, rollback, public-check, or HTTP-code path under the site before the remote body acquires the lock. The body validates and removes only the three exact transport entries whose hashes prove they are this invocation's inputs. If spooling fails before the body runs, retain and report the exact unique directory for inspected manual cleanup; do not use a glob or recursive deletion.

- [ ] **Step 4: Install under compare-and-swap and automatic rollback**

Run one remote Bash session. Its trap is installed before the first live-target mutation. It handles both a pre-existing page and an originally absent page, and retains rollback copies until server-local and public checks have passed:

```bash
ssh activitycontext.work bash -s -- \
  "$deploy_id" "$expected_index_before_sha" "$expected_index_after_sha" \
  "$expected_page_sha" "$expected_page_before_state" /var/www/wamason.com/ayllu \
  /home/tony/.wamason-ayllu-deploy.lock "$transport_dir" \
  https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/ \
  https://wamason.com/ayllu/ none <<'REMOTE'
set -Eeuo pipefail
set +E

deploy_id=$1
expected_index_before_sha=$2
expected_index_after_sha=$3
expected_page_sha=$4
expected_page_before_state=$5
site_dir_input=$6
lock_path=$7
transport_dir_input=$8
page_url=$9
index_url=${10}
failpoint=${11}

case $deploy_id in
  ''|*[!A-Za-z0-9._-]*) printf 'unsafe deployment id: %s\n' "$deploy_id" >&2; exit 64 ;;
esac
case $expected_page_before_state in
  absent) ;;
  ''|*[!0-9a-f]*) printf 'invalid expected live page state: %s\n' "$expected_page_before_state" >&2; exit 64 ;;
  *)
    if test "${#expected_page_before_state}" -ne 64; then
      printf 'invalid expected live page SHA-256: %s\n' "$expected_page_before_state" >&2
      exit 64
    fi
    ;;
esac
case $failpoint in
  none|before-mutation|after-page|after-both|unknown-page|unknown-index|missing-page|missing-index|signal-after-page|signal-after-both) ;;
  *) printf 'invalid deployment failpoint: %s\n' "$failpoint" >&2; exit 64 ;;
esac

site_dir=$(realpath -m -- "$site_dir_input") || {
  printf 'cannot canonicalize site directory: %s\n' "$site_dir_input" >&2
  exit 64
}
production_site_dir=$(realpath -m -- /var/www/wamason.com/ayllu)
case $site_dir in
  "$production_site_dir"|"$production_site_dir"/*)
    if test "$failpoint" != none; then
      printf 'test failpoints are forbidden for canonical production tree: %s\n' "$site_dir" >&2
      exit 64
    fi
    ;;
esac

lock_dir=$(realpath -m -- "$(dirname -- "$lock_path")")
page_dir=$site_dir/a-receipt-for-what-we-chose-not-to-remember
page_live=$page_dir/index.html
index_live=$site_dir/index.html
page_pending=$page_dir/.index.html.$deploy_id.pending
index_pending=$site_dir/.index.html.$deploy_id.pending
index_guard=$site_dir/.index.html.$deploy_id.guard
page_rollback=$page_dir/.index.html.$deploy_id.rollback
index_rollback=$site_dir/.index.html.$deploy_id.rollback
page_public_check=$page_dir/.index.html.$deploy_id.public-check
index_public_check=$site_dir/.index.html.$deploy_id.public-check
page_code_output=$page_dir/.index.html.$deploy_id.http-code
index_code_output=$site_dir/.index.html.$deploy_id.http-code

page_transport=
index_transport=
guard_transport=
page_before_state=$expected_page_before_state
page_dir_created=0
page_attempted=0
index_attempted=0
page_restored=0
index_restored=0
ownership_conflict=0
recovery_failure=0
transport_dir_owned=0
page_transport_owned=0
index_transport_owned=0
guard_transport_owned=0
page_pending_created=0
index_pending_created=0
index_guard_created=0
page_rollback_created=0
index_rollback_created=0
page_public_check_created=0
index_public_check_created=0
page_code_output_created=0
index_code_output_created=0
transport_dir_identity=
page_transport_identity=
index_transport_identity=
guard_transport_identity=
page_dir_identity=
page_pending_identity=
index_pending_identity=
index_guard_identity=
page_rollback_identity=
index_rollback_identity=
page_public_check_identity=
index_public_check_identity=
page_code_output_identity=
index_code_output_identity=
empty_sha=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

entry_exists() {
  test -e "$1" || test -L "$1"
}

path_identity() {
  stat -c '%d:%i' -- "$1"
}

regular_sha() {
  test -f "$1" && test ! -L "$1" || return 1
  sha256sum -- "$1" | awk 'NR == 1 { print $1 }'
}

require_regular_sha() {
  required_path=$1
  required_sha=$2
  required_label=$3
  if test -L "$required_path" || test ! -f "$required_path"; then
    printf 'required %s is not an owned regular file: %s\n' "$required_label" "$required_path" >&2
    return 1
  fi
  actual_sha=$(regular_sha "$required_path") || return 1
  if test "$actual_sha" != "$required_sha"; then
    printf 'required %s hash mismatch: %s\n' "$required_label" "$required_path" >&2
    return 1
  fi
}

require_absent_entry() {
  absent_path=$1
  absent_label=$2
  if entry_exists "$absent_path"; then
    printf 'deployment artifact collision at %s: %s\n' "$absent_label" "$absent_path" >&2
    return 1
  fi
}

reserve_owned_file() {
  reserve_path=$1
  reserve_label=$2
  require_absent_entry "$reserve_path" "$reserve_label" || return 1
  if ! (set -C; : >"$reserve_path") 2>/dev/null; then
    printf 'could not exclusively create %s: %s\n' "$reserve_label" "$reserve_path" >&2
    return 1
  fi
  if test -L "$reserve_path" || test ! -f "$reserve_path"; then
    printf 'created %s is not a regular file: %s\n' "$reserve_label" "$reserve_path" >&2
    return 1
  fi
}

same_owned_entry() {
  owned_path=$1
  owned_identity=$2
  test -f "$owned_path" && test ! -L "$owned_path" || return 1
  test "$(path_identity "$owned_path")" = "$owned_identity"
}

owns_installed_bytes() {
  target=$1
  installed_sha=$2
  current_sha=$(regular_sha "$target") || return 1
  test "$current_sha" = "$installed_sha"
}

owns_snapshot_bytes() {
  snapshot=$1
  snapshot_created=$2
  snapshot_identity=$3
  snapshot_sha=$4
  test "$snapshot_created" = 1 || return 1
  same_owned_entry "$snapshot" "$snapshot_identity" || return 1
  current_sha=$(regular_sha "$snapshot") || return 1
  test "$current_sha" = "$snapshot_sha"
}

cleanup_owned_file() {
  cleanup_flag_name=$1
  cleanup_path=$2
  cleanup_identity=$3
  cleanup_label=$4
  test "${!cleanup_flag_name}" = 1 || return 0
  if ! same_owned_entry "$cleanup_path" "$cleanup_identity"; then
    recovery_failure=1
    printf 'cleanup refused changed or missing %s; evidence retained: %s\n' "$cleanup_label" "$cleanup_path" >&2
    return 1
  fi
  if rm -f -- "$cleanup_path"; then
    printf -v "$cleanup_flag_name" '%s' 0
    return 0
  fi
  recovery_failure=1
  printf 'cleanup failed removing %s; evidence retained: %s\n' "$cleanup_label" "$cleanup_path" >&2
  return 1
}

cleanup_owned_directory() {
  cleanup_flag_name=$1
  cleanup_path=$2
  cleanup_identity=$3
  cleanup_label=$4
  test "${!cleanup_flag_name}" = 1 || return 0
  if test -L "$cleanup_path" || test ! -d "$cleanup_path" || \
      test "$(path_identity "$cleanup_path")" != "$cleanup_identity"; then
    recovery_failure=1
    printf 'cleanup refused changed or missing %s; evidence retained: %s\n' "$cleanup_label" "$cleanup_path" >&2
    return 1
  fi
  if rmdir -- "$cleanup_path"; then
    printf -v "$cleanup_flag_name" '%s' 0
    return 0
  fi
  recovery_failure=1
  printf 'cleanup failed removing %s; evidence retained: %s\n' "$cleanup_label" "$cleanup_path" >&2
  return 1
}

cleanup_owned_nonrollback_artifacts() {
  cleanup_owned_file page_pending_created "$page_pending" "$page_pending_identity" 'page pending' || :
  cleanup_owned_file index_pending_created "$index_pending" "$index_pending_identity" 'index pending' || :
  cleanup_owned_file index_guard_created "$index_guard" "$index_guard_identity" 'index guard' || :
  cleanup_owned_file page_public_check_created "$page_public_check" "$page_public_check_identity" 'page public check' || :
  cleanup_owned_file index_public_check_created "$index_public_check" "$index_public_check_identity" 'index public check' || :
  cleanup_owned_file page_code_output_created "$page_code_output" "$page_code_output_identity" 'page HTTP code output' || :
  cleanup_owned_file index_code_output_created "$index_code_output" "$index_code_output_identity" 'index HTTP code output' || :
  cleanup_owned_file page_transport_owned "$page_transport" "$page_transport_identity" 'page transport' || :
  cleanup_owned_file index_transport_owned "$index_transport" "$index_transport_identity" 'index transport' || :
  cleanup_owned_file guard_transport_owned "$guard_transport" "$guard_transport_identity" 'guard transport' || :
  cleanup_owned_directory transport_dir_owned "$transport_dir" "$transport_dir_identity" 'transport directory' || :
}

rollback() {
  status=$1
  trap - ERR INT TERM HUP
  set +e
  printf 'deployment rollback started: status=%s\n' "$status" >&2

  if test "$index_attempted" = 1; then
    if ! entry_exists "$index_live"; then
      ownership_conflict=1
      printf 'rollback refused missing index target; evidence retained: %s\n' "$index_rollback" >&2
    elif ! owns_installed_bytes "$index_live" "$expected_index_after_sha"; then
      ownership_conflict=1
      printf 'rollback refused unknown index bytes; evidence retained: %s\n' "$index_rollback" >&2
    elif ! owns_snapshot_bytes "$index_rollback" "$index_rollback_created" "$index_rollback_identity" "$expected_index_before_sha"; then
      recovery_failure=1
      printf 'rollback snapshot invalid for index; evidence retained: %s\n' "$index_rollback" >&2
    elif mv -f -- "$index_rollback" "$index_live"; then
      index_rollback_created=0
      index_restored=1
    else
      recovery_failure=1
      printf 'rollback failed restoring index; evidence retained: %s\n' "$index_rollback" >&2
    fi
  fi

  if test "$page_attempted" = 1; then
    if ! entry_exists "$page_live"; then
      ownership_conflict=1
      printf 'rollback refused missing page target; evidence retained: %s\n' "$page_rollback" >&2
    elif ! owns_installed_bytes "$page_live" "$expected_page_sha"; then
      ownership_conflict=1
      printf 'rollback refused unknown page bytes; evidence retained: %s\n' "$page_rollback" >&2
    elif test "$page_before_state" = absent; then
      if ! owns_snapshot_bytes "$page_rollback" "$page_rollback_created" "$page_rollback_identity" "$empty_sha"; then
        recovery_failure=1
        printf 'rollback marker invalid for absent page; evidence retained: %s\n' "$page_rollback" >&2
      elif rm -f -- "$page_live"; then
        page_restored=1
      else
        recovery_failure=1
        printf 'rollback failed removing page; evidence retained: %s\n' "$page_rollback" >&2
      fi
    elif ! owns_snapshot_bytes "$page_rollback" "$page_rollback_created" "$page_rollback_identity" "$page_before_state"; then
      recovery_failure=1
      printf 'rollback snapshot invalid for page; evidence retained: %s\n' "$page_rollback" >&2
    elif mv -f -- "$page_rollback" "$page_live"; then
      page_rollback_created=0
      page_restored=1
    else
      recovery_failure=1
      printf 'rollback failed restoring page; evidence retained: %s\n' "$page_rollback" >&2
    fi
  fi

  cleanup_owned_nonrollback_artifacts
  if test "$recovery_failure" = 0 && test "$index_rollback_created" = 1 && \
      { test "$index_attempted" = 0 || test "$index_restored" = 1; }; then
    cleanup_owned_file index_rollback_created "$index_rollback" "$index_rollback_identity" 'index rollback' || :
  fi
  if test "$recovery_failure" = 0 && test "$page_rollback_created" = 1 && \
      { test "$page_attempted" = 0 || test "$page_restored" = 1; }; then
    cleanup_owned_file page_rollback_created "$page_rollback" "$page_rollback_identity" 'page rollback' || :
  fi
  if test "$recovery_failure" = 0 && test "$page_dir_created" = 1 && \
      { test "$page_attempted" = 0 || test "$page_restored" = 1; }; then
    cleanup_owned_directory page_dir_created "$page_dir" "$page_dir_identity" 'page directory' || :
  fi

  if test "$recovery_failure" = 1; then
    status=77
  elif test "$ownership_conflict" = 1; then
    status=76
  fi
  test "$status" -ne 0 || status=1
  exit "$status"
}

signal_rollback() {
  signal_name=$1
  signal_status=$2
  printf 'deployment received %s; rolling back\n' "$signal_name" >&2
  rollback "$signal_status"
}

exec 9>"$lock_path"
flock -n 9 || {
  printf 'deployment lock busy; transport retained at %s\n' "$transport_dir_input" >&2
  exit 75
}
trap 'rollback "$?"' ERR
trap 'signal_rollback HUP 129' HUP
trap 'signal_rollback INT 130' INT
trap 'signal_rollback TERM 143' TERM

if test -L "$transport_dir_input" || test ! -d "$transport_dir_input"; then
  printf 'transport directory is not an owned real directory: %s\n' "$transport_dir_input" >&2
  false
fi
transport_dir=$(realpath -e -- "$transport_dir_input")
if test "$(dirname -- "$transport_dir")" != "$lock_dir" || \
    test "${transport_dir##*/}" != ".wamason-ayllu-transport.$deploy_id" || \
    test "$(stat -c '%u' -- "$transport_dir")" != "$(id -u)" || \
    test "$(stat -c '%a' -- "$transport_dir")" != 700; then
  printf 'transport directory ownership contract failed: %s\n' "$transport_dir" >&2
  false
fi
case $transport_dir in
  "$site_dir"|"$site_dir"/*)
    printf 'transport directory must be outside document root: %s\n' "$transport_dir" >&2
    false
    ;;
esac
page_transport=$transport_dir/page.html
index_transport=$transport_dir/index.after.html
guard_transport=$transport_dir/index.before.html
require_regular_sha "$page_transport" "$expected_page_sha" 'page transport'
require_regular_sha "$index_transport" "$expected_index_after_sha" 'index transport'
require_regular_sha "$guard_transport" "$expected_index_before_sha" 'guard transport'
transport_dir_identity=$(path_identity "$transport_dir")
page_transport_identity=$(path_identity "$page_transport")
index_transport_identity=$(path_identity "$index_transport")
guard_transport_identity=$(path_identity "$guard_transport")
transport_dir_owned=1
page_transport_owned=1
index_transport_owned=1
guard_transport_owned=1

if test -L "$site_dir" || test ! -d "$site_dir"; then
  printf 'canonical site directory is not a real directory: %s\n' "$site_dir" >&2
  false
fi
require_regular_sha "$index_live" "$expected_index_before_sha" 'initial live index'
if entry_exists "$page_dir"; then
  if test -L "$page_dir" || test ! -d "$page_dir"; then
    printf 'live page directory is not a real directory: %s\n' "$page_dir" >&2
    false
  fi
  if test "$page_before_state" = absent; then
    if entry_exists "$page_live"; then
      printf 'initial live page no longer matches expected absence: %s\n' "$page_live" >&2
      false
    fi
  else
    require_regular_sha "$page_live" "$page_before_state" 'initial live page'
  fi
else
  if test "$page_before_state" != absent; then
    printf 'required initial live page is missing: %s\n' "$page_live" >&2
    false
  fi
  mkdir -- "$page_dir"
  page_dir_created=1
  page_dir_identity=$(path_identity "$page_dir")
fi

for artifact in "$page_pending" "$index_pending" "$index_guard" \
  "$page_rollback" "$index_rollback" "$page_public_check" \
  "$index_public_check" "$page_code_output" "$index_code_output"; do
  require_absent_entry "$artifact" 'live-adjacent path'
done

reserve_owned_file "$page_pending" 'page pending'
page_pending_created=1
cp -p -- "$page_transport" "$page_pending"
page_pending_identity=$(path_identity "$page_pending")
reserve_owned_file "$index_pending" 'index pending'
index_pending_created=1
cp -p -- "$index_transport" "$index_pending"
index_pending_identity=$(path_identity "$index_pending")
reserve_owned_file "$index_guard" 'index guard'
index_guard_created=1
cp -p -- "$guard_transport" "$index_guard"
index_guard_identity=$(path_identity "$index_guard")
reserve_owned_file "$page_public_check" 'page public check'
page_public_check_created=1
page_public_check_identity=$(path_identity "$page_public_check")
reserve_owned_file "$index_public_check" 'index public check'
index_public_check_created=1
index_public_check_identity=$(path_identity "$index_public_check")
reserve_owned_file "$page_code_output" 'page HTTP code output'
page_code_output_created=1
page_code_output_identity=$(path_identity "$page_code_output")
reserve_owned_file "$index_code_output" 'index HTTP code output'
index_code_output_created=1
index_code_output_identity=$(path_identity "$index_code_output")
chmod 0644 "$page_pending" "$index_pending"

cmp -s -- "$index_live" "$index_guard" || {
  printf 'initial live index bytes do not match transported guard\n' >&2
  false
}
reserve_owned_file "$index_rollback" 'index rollback'
index_rollback_created=1
cp -p -- "$index_live" "$index_rollback"
index_rollback_identity=$(path_identity "$index_rollback")
reserve_owned_file "$page_rollback" 'page rollback'
page_rollback_created=1
if test "$page_before_state" != absent; then
  cp -p -- "$page_live" "$page_rollback"
fi
page_rollback_identity=$(path_identity "$page_rollback")

if test "$failpoint" = before-mutation; then false; fi

require_regular_sha "$index_live" "$expected_index_before_sha" 'pre-mutation live index'
cmp -s -- "$index_live" "$index_guard" || {
  printf 'pre-mutation live index bytes do not match guard\n' >&2
  false
}
if test "$page_before_state" = absent; then
  if entry_exists "$page_live"; then
    printf 'pre-mutation page is no longer absent: %s\n' "$page_live" >&2
    false
  fi
else
  require_regular_sha "$page_live" "$page_before_state" 'pre-mutation live page'
fi

# Each rename is atomic, but the pair has an irreducible visibility window.
page_attempted=1
mv -f -- "$page_pending" "$page_live"
page_pending_created=0
if test "$failpoint" = unknown-page; then printf 'unknown page\n' >"$page_live"; false; fi
if test "$failpoint" = missing-page; then rm -f -- "$page_live"; false; fi
if test "$failpoint" = after-page; then false; fi
if test "$failpoint" = signal-after-page; then kill -STOP "$$"; fi
index_attempted=1
mv -f -- "$index_pending" "$index_live"
index_pending_created=0
if test "$failpoint" = unknown-index; then printf 'unknown index\n' >"$index_live"; false; fi
if test "$failpoint" = missing-index; then rm -f -- "$index_live"; false; fi
if test "$failpoint" = after-both; then false; fi
if test "$failpoint" = signal-after-both; then kill -STOP "$$"; fi

require_regular_sha "$page_live" "$expected_page_sha" 'installed page'
require_regular_sha "$index_live" "$expected_index_after_sha" 'installed index'
grep -Fq 'A Receipt for What We Chose Not to Remember' "$page_live"
grep -Fq '/ayllu/a-receipt-for-what-we-chose-not-to-remember/' "$index_live"

curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' \
  --output "$page_public_check" --write-out '%{http_code}\n' "$page_url" >"$page_code_output"
curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' \
  --output "$index_public_check" --write-out '%{http_code}\n' "$index_url" >"$index_code_output"
IFS= read -r page_code <"$page_code_output"
IFS= read -r index_code <"$index_code_output"
test "$page_code" = 200
test "$index_code" = 200
require_regular_sha "$page_public_check" "$expected_page_sha" 'public page'
require_regular_sha "$index_public_check" "$expected_index_after_sha" 'public index'

trap - ERR INT TERM HUP
set +e
cleanup_owned_nonrollback_artifacts
if test "$recovery_failure" = 0; then
  cleanup_owned_file index_rollback_created "$index_rollback" "$index_rollback_identity" 'index rollback' || :
fi
if test "$recovery_failure" = 0; then
  cleanup_owned_file page_rollback_created "$page_rollback" "$page_rollback_identity" 'page rollback' || :
fi
if test "$recovery_failure" = 1; then
  exit 77
fi
printf 'staged publication validated: page=%s index=%s\n' "$expected_page_sha" "$expected_index_after_sha"
REMOTE
```

Expected: `staged publication validated` with both expected hashes. A queued invocation exits nonzero without live mutation if the locked page differs from its caller-captured expected state; the same page precondition is repeated immediately before mutation. Any command error or caught signal before success invokes the trap exactly once and exits nonzero. For cooperative lock participants, each attempted target is restored to prior bytes or the absent-page state only while the live bytes still equal this deployment's installed hash. A detected unknown or missing target is preserved with corresponding rollback evidence and status 76. Restore, removal, or owned-artifact cleanup failure retains available evidence and takes precedence as status 77. A target whose rename was never attempted is not restored. Hash and identity checks remain best-effort against a writer that ignores the lock because the check and rename/removal are not atomic together. Stop at the first failed safety gate; diagnose and report rather than retrying blindly. The verified full-site archive remains the recovery point if the remote shell itself is forcibly killed before a trap can run.

- [ ] **Step 5: Independently verify and preserve evidence**

Run:

```bash
curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' --write-out '%{http_code}\n' https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/ -o "$stage_dir/public-page.html"
curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' --write-out '%{http_code}\n' https://wamason.com/ayllu/ -o "$stage_dir/public-index.html"
cmp "$stage_dir/page.html" "$stage_dir/public-page.html"
cmp "$stage_dir/index.after.html" "$stage_dir/public-index.html"
python "$stage_dir/validate_page.py" "$stage_dir/public-page.html" .superpowers/sdd/2026-07-26-ayllu-codex-stone/author-copy.md
grep -Fq '/ayllu/a-receipt-for-what-we-chose-not-to-remember/' "$stage_dir/public-index.html"
ssh activitycontext.work bash -s -- "$backup_path" "$transport_dir" \
  "$page_pending" "$index_pending" "$index_guard" "$page_rollback" \
  "$index_rollback" "$page_public_check" "$index_public_check" \
  "$page_code_output" "$index_code_output" <<'REMOTE_CHECK'
set -eu
backup_path=$1
transport_dir=$2
shift 2
test -s "$backup_path"
tar -tzf "$backup_path" >/dev/null
test ! -e "$transport_dir" && test ! -L "$transport_dir"
for artifact in "$@"; do
  test ! -e "$artifact" && test ! -L "$artifact"
done
REMOTE_CHECK
```

Expected: two HTTP `200` responses, byte-for-byte equality for both public files, expanded validator success, readable backup, and absence (including dangling symlinks) of the exact transport, pending, guard, rollback, public-check, and HTTP-code paths. Preserve the verified backups and local staging directory through final reporting.

---

## Final Verification

Run:

```bash
curl --fail --silent --show-error --location --write-out '%{http_code}\n' --output /dev/null https://wamason.com/ayllu/
curl --fail --silent --show-error --location --write-out '%{http_code}\n' --output /dev/null https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/
ssh activitycontext.work "test -s '$backup_path' && tar -tzf '$backup_path' >/dev/null"
git -C /home/tony/projects/qhaway status --short --branch
```

Expected: two `200` responses, a readable preserved backup, and no uncommitted qhaway changes caused by publication.
