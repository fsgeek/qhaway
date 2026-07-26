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
- A failed in-session post-install check triggers restoration from the adjacent rollback copies; the verified full-site backup remains the fallback if the remote shell cannot run its trap.
- Require the live index to match both its captured SHA-256 digest and exact captured bytes immediately before the first live-target mutation.
- Stage pending files and rollback copies adjacent to their targets on the same filesystem, install each target with atomic `mv`, and keep a remote `ERR`/`INT`/`TERM`/`HUP` restoration trap active through server-local and public checks.
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

- [ ] **Step 3: Capture install guards and stage on the target filesystem**

Keep these exact values for the remaining steps:

```bash
deploy_id=$(date -u +%Y%m%d-%H%M%S)
site_dir=/var/www/wamason.com/ayllu
page_transport="$site_dir/.a-receipt-for-what-we-chose-not-to-remember.$deploy_id.pending"
index_pending="$site_dir/.index.html.$deploy_id.pending"
index_guard="$site_dir/.index.html.$deploy_id.guard"
expected_index_before_sha=$(sha256sum "$stage_dir/index.before.html" | awk '{print $1}')
expected_index_after_sha=$(sha256sum "$stage_dir/index.after.html" | awk '{print $1}')
expected_page_sha=$(sha256sum "$stage_dir/page.html" | awk '{print $1}')
page_before_state=$(ssh activitycontext.work 'set -eu; page=/var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/index.html; if test -e "$page"; then sha256sum "$page" | cut -d " " -f 1; else printf "absent\n"; fi')

ssh activitycontext.work "set -eu; test ! -e '$page_transport'; test ! -e '$index_pending'; test ! -e '$index_guard'"
scp "$stage_dir/page.html" "activitycontext.work:$page_transport"
scp "$stage_dir/index.after.html" "activitycontext.work:$index_pending"
scp "$stage_dir/index.before.html" "activitycontext.work:$index_guard"
ssh activitycontext.work "set -eu; test -s '$page_transport'; test -s '$index_pending'; test -s '$index_guard'; test \"\$(sha256sum '$page_transport' | awk '{print \$1}')\" = '$expected_page_sha'; test \"\$(sha256sum '$index_pending' | awk '{print \$1}')\" = '$expected_index_after_sha'; test \"\$(sha256sum '$index_guard' | awk '{print \$1}')\" = '$expected_index_before_sha'"
```

The transport and index files are explicit adjacent paths under the target site, so subsequent copies and renames stay on the same filesystem. This staging does not change either live file.

- [ ] **Step 4: Install under compare-and-swap and automatic rollback**

Run one remote Bash session. Its trap is installed before the first live-target mutation. It handles both a pre-existing page and an originally absent page, and retains rollback copies until server-local and public checks have passed:

```bash
ssh activitycontext.work bash -s -- \
  "$deploy_id" "$expected_index_before_sha" "$expected_index_after_sha" \
  "$expected_page_sha" "$page_before_state" <<'REMOTE'
set -Eeuo pipefail

deploy_id=$1
expected_index_before_sha=$2
expected_index_after_sha=$3
expected_page_sha=$4
page_before_state=$5
site_dir=/var/www/wamason.com/ayllu
page_dir=$site_dir/a-receipt-for-what-we-chose-not-to-remember
page_live=$page_dir/index.html
index_live=$site_dir/index.html
page_transport=$site_dir/.a-receipt-for-what-we-chose-not-to-remember.$deploy_id.pending
page_pending=$page_dir/.index.html.$deploy_id.pending
index_pending=$site_dir/.index.html.$deploy_id.pending
index_guard=$site_dir/.index.html.$deploy_id.guard
page_rollback=$page_dir/.index.html.$deploy_id.rollback
index_rollback=$site_dir/.index.html.$deploy_id.rollback
page_public_check=$page_dir/.index.html.$deploy_id.public-check
index_public_check=$site_dir/.index.html.$deploy_id.public-check
page_rollback_ready=0
index_rollback_ready=0

rollback() {
  status=$?
  trap - ERR INT TERM HUP
  set +e
  if test "$index_rollback_ready" = 1; then
    mv -f -- "$index_rollback" "$index_live"
  fi
  if test "$page_before_state" = absent; then
    rm -f -- "$page_live" "$page_pending" "$page_rollback" "$page_public_check"
    rmdir -- "$page_dir" 2>/dev/null || true
  elif test "$page_rollback_ready" = 1; then
    mv -f -- "$page_rollback" "$page_live"
  fi
  rm -f -- "$page_transport" "$index_pending" "$index_guard" "$index_public_check"
  test "$status" -ne 0 || status=1
  exit "$status"
}
trap rollback ERR INT TERM HUP

test -s "$page_transport"
test -s "$index_pending"
test -s "$index_guard"
test "$(sha256sum "$page_transport" | awk '{print $1}')" = "$expected_page_sha"
test "$(sha256sum "$index_pending" | awk '{print $1}')" = "$expected_index_after_sha"
test "$(sha256sum "$index_guard" | awk '{print $1}')" = "$expected_index_before_sha"

if test "$page_before_state" = absent; then
  test ! -e "$page_live"
  mkdir -p -- "$page_dir"
else
  test -f "$page_live"
  test "$(sha256sum "$page_live" | awk '{print $1}')" = "$page_before_state"
fi

cp -p -- "$index_live" "$index_rollback"
index_rollback_ready=1
if test "$page_before_state" != absent; then
  cp -p -- "$page_live" "$page_rollback"
  page_rollback_ready=1
fi
cp -p -- "$page_transport" "$page_pending"
chmod 0644 "$page_pending" "$index_pending"

# Install-time compare-and-swap: abort before either live rename if the index moved.
test "$(sha256sum "$index_live" | awk '{print $1}')" = "$expected_index_before_sha"
cmp -s -- "$index_live" "$index_guard"

# Each rename is atomic, but the pair has an irreducible visibility window.
mv -f -- "$page_pending" "$page_live"
mv -f -- "$index_pending" "$index_live"

test "$(sha256sum "$page_live" | awk '{print $1}')" = "$expected_page_sha"
test "$(sha256sum "$index_live" | awk '{print $1}')" = "$expected_index_after_sha"
grep -Fq 'A Receipt for What We Chose Not to Remember' "$page_live"
grep -Fq '/ayllu/a-receipt-for-what-we-chose-not-to-remember/' "$index_live"

page_code=$(curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' --output "$page_public_check" --write-out '%{http_code}' https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/)
index_code=$(curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' --output "$index_public_check" --write-out '%{http_code}' https://wamason.com/ayllu/)
test "$page_code" = 200
test "$index_code" = 200
test "$(sha256sum "$page_public_check" | awk '{print $1}')" = "$expected_page_sha"
test "$(sha256sum "$index_public_check" | awk '{print $1}')" = "$expected_index_after_sha"

trap - ERR INT TERM HUP
rm -f -- "$page_transport" "$index_guard" "$page_rollback" "$index_rollback" "$page_public_check" "$index_public_check"
printf 'staged publication validated: page=%s index=%s\n' "$expected_page_sha" "$expected_index_after_sha"
REMOTE
```

Expected: `staged publication validated` with both expected hashes. Any command error or caught signal before that point invokes the trap, restores the prior index, restores the prior page bytes or absent-page state, and exits nonzero. Stop at that first failed safety gate; diagnose and report rather than retrying blindly. The verified full-site archive remains the recovery point if the remote shell itself is forcibly killed before a trap can run.

- [ ] **Step 5: Independently verify and preserve evidence**

Run:

```bash
curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' --write-out '%{http_code}\n' https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/ -o "$stage_dir/public-page.html"
curl --fail --silent --show-error --location --header 'Cache-Control: no-cache' --write-out '%{http_code}\n' https://wamason.com/ayllu/ -o "$stage_dir/public-index.html"
cmp "$stage_dir/page.html" "$stage_dir/public-page.html"
cmp "$stage_dir/index.after.html" "$stage_dir/public-index.html"
python "$stage_dir/validate_page.py" "$stage_dir/public-page.html" .superpowers/sdd/2026-07-26-ayllu-codex-stone/author-copy.md
grep -Fq '/ayllu/a-receipt-for-what-we-chose-not-to-remember/' "$stage_dir/public-index.html"
ssh activitycontext.work "set -eu; test -s '$backup_path'; tar -tzf '$backup_path' >/dev/null; test ! -e '$page_transport'; test ! -e '$index_pending'; test ! -e '$index_guard'; test ! -e '/var/www/wamason.com/ayllu/.index.html.$deploy_id.rollback'; test ! -e '/var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/.index.html.$deploy_id.rollback'"
```

Expected: two HTTP `200` responses, byte-for-byte equality for both public files, expanded validator success, readable backup, and absence of every exact pending/guard/rollback path. Preserve the verified backups and local staging directory through final reporting.

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
