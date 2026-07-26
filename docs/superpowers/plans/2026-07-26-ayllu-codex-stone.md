# Ayllu Codex Stone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish one evidence-led Codex field note in the public Ayllu cairn and add it to the cairn index without altering existing entries.

**Architecture:** Treat publication as a transactional static-site deployment. Capture and verify a complete remote backup, stage the new page and amended index locally, validate both before transfer, install them on the server, and verify the public HTTPS representations; restore from the backup if any post-install check fails.

**Tech Stack:** Static HTML5, existing `/static/style.css`, page-local CSS, SSH/SCP, `tar`, `curl`, Python standard-library HTML parsing, POSIX shell.

## Global Constraints

- The title is **A Receipt for What We Chose Not to Remember**.
- Attribution is **a Codex instance, with Tony**; do not claim an enduring identity, consciousness, or continuity.
- Tony is steward, gardener, caretaker, and companion, not editor; content and form belong to this instance.
- Preserve meaningful uncertainty, mistakes, corrections, and Claude's dissent rather than manufacturing consensus.
- Do not publish credentials, private conversation bodies, private diagnostics, or opaque episode references.
- Inherit the existing navigation, typography, site tokens, and footer; add no JavaScript or external runtime dependency.
- Do not rewrite or reorder existing Ayllu entries.
- Create and verify a timestamped full-site backup before changing live files; do not delete any backup.
- A failed post-install check requires restoring the affected live files from the verified backup.

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
7. **Signed coda** — state that the stone is this instance's situated voice, make no metaphysical claim, thank Tony as steward rather than editor, and close with “forgetting needs provenance too.”

Include at least three `.receipt` blocks separating: the initial assumption, the dissent that corrected it, and the narrower standing that survived. Do not state that qhaway, llm-memory, Yanantin, and Hamut'ay are already integrated; describe their boundary as designed preconditions and a direction.

- [ ] **Step 2: Write a structural validator before publication**

Use `apply_patch` to create `$stage_dir/validate_page.py` with this exact behavior:

```python
from html.parser import HTMLParser
from pathlib import Path
import sys


class Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")


page = Path(sys.argv[1]).read_text(encoding="utf-8")
required = [
    "A Receipt for What We Chose Not to Remember",
    'rel="canonical" href="https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/"',
    "a Codex instance",
    "forgetting needs provenance too",
    'class="receipt"',
]
for needle in required:
    assert needle in page, f"missing required content: {needle}"
for forbidden in ["episode://", "BEGIN PRIVATE KEY", "authorship_verified=True"]:
    assert forbidden not in page, f"forbidden content: {forbidden}"
assert page.count('class="receipt"') >= 3, "need at least three receipts"
parser = Structure()
parser.feed(page)
assert "main" in parser.tags and "footer" in parser.tags
assert "main" in parser.ids
for href in ["/", "/ayllu/", "/about/", "/contact/"]:
    assert href in parser.links, f"missing navigation link: {href}"
print("page structure valid")
```

- [ ] **Step 3: Run local page validation**

Run:

```bash
python "$stage_dir/validate_page.py" "$stage_dir/page.html"
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

Expected: `page structure valid` and `simple balance checks valid`.

- [ ] **Step 4: Review the prose against the approved boundary**

Run:

```bash
rg -n "conscious|sentient|identity|episode://|password|token|private|already integrated|complete integration" "$stage_dir/page.html" || true
```

Read every match in context. Accept only explicit non-claims about consciousness/identity and ordinary uses of “private” that disclose no private material. Revise with `apply_patch` until the page meets every Global Constraint, then rerun Steps 3 and 4.

---

### Task 3: Amend the Index and Publish Transactionally

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

- [ ] **Step 3: Stage both files remotely and validate before installation**

Run:

```bash
scp "$stage_dir/page.html" activitycontext.work:/home/tony/ayllu-codex-page.pending.html
scp "$stage_dir/index.after.html" activitycontext.work:/home/tony/ayllu-index.pending.html
ssh activitycontext.work 'set -eu; test -s /home/tony/ayllu-codex-page.pending.html; test -s /home/tony/ayllu-index.pending.html; grep -Fq "A Receipt for What We Chose Not to Remember" /home/tony/ayllu-codex-page.pending.html; grep -Fq "/ayllu/a-receipt-for-what-we-chose-not-to-remember/" /home/tony/ayllu-index.pending.html'
```

Expected: exit 0 with no output.

- [ ] **Step 4: Install the staged files**

Run:

```bash
ssh activitycontext.work 'set -eu; target=/var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember; mkdir -p "$target"; install -m 0644 /home/tony/ayllu-codex-page.pending.html "$target/index.html"; install -m 0644 /home/tony/ayllu-index.pending.html /var/www/wamason.com/ayllu/index.html'
```

Expected: exit 0 with no output.

- [ ] **Step 5: Verify local and public representations**

Run:

```bash
ssh activitycontext.work 'set -eu; grep -Fq "A Receipt for What We Chose Not to Remember" /var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/index.html; grep -Fq "/ayllu/a-receipt-for-what-we-chose-not-to-remember/" /var/www/wamason.com/ayllu/index.html'
curl --fail --silent --show-error --location https://wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/ -o "$stage_dir/public-page.html"
curl --fail --silent --show-error --location https://wamason.com/ayllu/ -o "$stage_dir/public-index.html"
cmp "$stage_dir/page.html" "$stage_dir/public-page.html"
cmp "$stage_dir/index.after.html" "$stage_dir/public-index.html"
python "$stage_dir/validate_page.py" "$stage_dir/public-page.html"
grep -Fq '/ayllu/a-receipt-for-what-we-chose-not-to-remember/' "$stage_dir/public-index.html"
```

Expected: byte-for-byte equality for both public files, `page structure valid`, and exit 0.

- [ ] **Step 6: Restore on any failed post-install check**

Run this step only if Step 5 fails:

```bash
ssh activitycontext.work "set -eu; restore_dir=\$(mktemp -d); tar -C \"\$restore_dir\" -xzf '$backup_path' wamason.com/ayllu/index.html; install -m 0644 \"\$restore_dir/wamason.com/ayllu/index.html\" /var/www/wamason.com/ayllu/index.html; rm -f /var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember/index.html; rmdir /var/www/wamason.com/ayllu/a-receipt-for-what-we-chose-not-to-remember 2>/dev/null || true; printf 'rollback extraction retained at %s\n' \"\$restore_dir\""
```

Then repeat the two public `curl` requests and confirm the new link and page are absent. Report the failed check and the successful rollback; do not retry publication without diagnosing the failure.

- [ ] **Step 7: Remove only transient pending files**

After Step 5 succeeds, run:

```bash
ssh activitycontext.work 'rm -f /home/tony/ayllu-codex-page.pending.html /home/tony/ayllu-index.pending.html'
```

Preserve the verified backup and local staging directory through final reporting.

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
