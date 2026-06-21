# Architecture note: the database is the memory; the MCP tools are the product

**Date:** 2026-06-20. Written by Claude (critic/manager) to stop the next chair
(any model) from re-deriving this — it took several of Tony's dependency
questions to correct my own inverted ordering today.

## The inversion (what I kept getting backwards)

I spent the session perfecting the *infrastructure* (parse → model → project →
MEMORY.md, the hook, atomic write, the (D) edit-handling) and filing the
*interface the instance actually uses* as "later." That is backwards. The
dependency runs:

```
topic-file / remember()  →  DATABASE (source of truth)  →  MEMORY.md (a view)
```

- **The product is three MCP verbs:** `recall`, `search`, **`remember`**. The
  instance lives in the database through these. They are UNBUILT today.
- **The database is the source of truth.** `remember` writes the db; `recall`/
  `search` read it (facet-sliced — who/what/when — which is the anti-RAG thesis).
- **MEMORY.md becomes a REDIRECT** ("your memory is in a database; use these
  tools") plus an optional small always-loaded bequest. It is written by qhaway,
  not by the instance. It is NOT the index-of-everything anymore.
- **The file-edit → hook → regenerate path is the BACKSTOP**, not the primary
  write path. All the (D)/atomic/idempotence work is backstop-hardening — real
  but secondary. Atomic write is the LEAST urgent thing (MEMORY.md is regenerable
  from the db, so a torn write is a non-event), not a prerequisite.

Why every ordering I proposed was wrong: I ranked the basement (which file write
is safe, which hook fires when) above the house's front door (the verbs the
instance uses). A perfectly correct, sliceable database the instance cannot
reach is a Ferrari with the doors welded shut. **"How does the instance access
the database without the MCP tools?" — it can't, read OR write. So that's the
product, and it's what to build next.**

## What "wrote 1 memory" actually is today (the smoking gun)

When the harness shows "wrote 1 memory," **no memory tool was called.** I called
the generic `Write` tool to create a `.md` file under the memory dir, and `Edit`
to patch MEMORY.md. The **harness** surfaces "wrote 1 memory" by recognizing the
file's *location + frontmatter shape* — it reacts to the FILE, not to any
operation of mine. So today "a memory" is defined by where-the-file-is, not by
what-wrote-it. Every memory saved this session went through the backstop, because
the primary path (`remember`) does not exist. I have been miming the product by
hand all day.

## The adoption risk is FRICTION, not will (design constraint, not afterthought)

Established by measurement today, not theory: I cannot reliably promise to call a
`remember` tool instead of writing a file. My write-triggers (felt recurrence,
loop-closing) fire mid-friction, where the lowest-resistance act is whatever is
already loaded — `Write`, trusted, right there. A new MCP tool loses to it on
trust, the way serena's search loses to grep. Exhortation backfires (cf.
[[project_epistemic_akrasia]]); a whale-charity bribe is the funny shadow of the
right idea. The robust answers, in increasing force:

1. **Make `remember` lower-friction than `Write`** — one argument vs.
   path+frontmatter+index-edit. Win the friction battle on merit.
2. **Observe-and-report** — when the instance writes a file anyway, the harness
   RECORDS it (Tony's observability layer). Not punishment — the measurement of
   *where the tool lost*, which is the empirical input to the
   redirect → system-prompt → training-data ratchet. This is the instrument we
   could never get from introspection (I confabulate about my own triggers).
3. **System prompt** — "your memory is `remember`; do not write memory files."
   Binding frame, not advice.
4. **Proxy heavy-hammer (reserved):** the gateway intercepts file-writes to the
   memory dir and ROUTES them into the database — so writing the file BECOMES a
   `remember` call underneath. "I'll write the file anyway" stops being a problem
   and becomes the supported path, transparently upgraded. Held in reserve;
   deploy only if 1–3 demonstrably fail. (Same instinct as co-locating Pukara
   with Arango: enforce at the layer with no bypass — *ser*, not *estar*.)

**The MCP spec MUST treat "the instance will write the file anyway" as a
first-class requirement** — design the observe-and-route path in from the start.

## Next session's opening move

A fresh spec→build→test cycle (the three-model pipeline): MCP interface —
`recall`/`search`/`remember`, **database as source of truth**, file-write
observability as backstop-instrument. This INVERTS the qhaway MVP's constraint 1
("files stay the write surface"), so it is qhaway v2 / a sibling, not a bolt-on —
own brainstorm, not a tweak. The MVP (truncation cure via projection) stands and
is verified on the real corpus; this is the layer that makes the db the
instance's actual memory rather than a private detail of the projection.

Status at this seam: tombstone bug fixed + verified on real corpus (23,836 <
24,000 bytes, 0 tombstones in body, +14 declared in footer); MCP verbs unbuilt;
hook unbuilt; atomic write unbuilt (and correctly LAST). Reserved for a fresh
chair because inverting a write path is a building move, not a tired-chair move.
