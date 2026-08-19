# Roadmap

> Foundation laid 2026-08-18. **Parked, not abandoned** — `auto_Interner` is the
> WIP project and the WIP limit is one.

## What this is

Curat0r turns work you have actually done into a résumé tailored to one posting.
It never writes a claim about you; it selects from blocks you wrote and verified.

## Phase 0 — foundation ✅ complete

1,425 lines, 101 tests, no runtime dependencies.

| Module | Does | Lines |
|---|---|---|
| `sources.py` | Ingestion sanction guard. Six sources, four material kinds. | 248 |
| `adjacency.py` | How close what you have is to what they want. Never satisfies a gap. | 202 |
| `drafts.py` | Payloads → draft blocks, always `_verified: false`. | 170 |
| `gaps.py` | Asks a question per gap instead of filling it. | 161 |
| `filters.py` | Drops practice repos, forks, profile READMEs — with a reason each. | 151 |
| `merge.py` | Re-ingest never overwrites your prose. Cross-source dedupe. | 143 |

The guarantees are in place and tested. What is missing is reach.

## Phase 1 — make one source real

**The `RepoFetcher` port has no implementation.** Everything downstream of it
works and is tested against fixtures; nothing has ever called GitHub.

- [ ] `GitHubFetcher` implementing `list_repos(owner)` against the public REST API
- [ ] Rate-limit handling and an unauthenticated path (60 req/hr is enough for one user)
- [ ] Cache responses to disk; a résumé run should not re-fetch a profile
- [ ] One integration test behind a flag, off by default

**Exit:** `curat0r ingest github.com/<user>` produces a corpus file, offline
tests still green.

## Phase 2 — the sources that carry work history

GitHub gives projects and nothing else. A résumé needs employment, and the 50%
coverage in the README is exactly that gap.

- [ ] LinkedIn export parser — the `Positions.csv` in the data archive
- [ ] Indeed profile résumé parser (reuses the DOCX reader)
- [ ] Kaggle: competitions and notebooks via the public API

**Exit:** a corpus with work history that did not come from a résumé.

## Phase 3 — the corpus becomes a thing you own

Right now the corpus is a JSON file passed around. It should persist.

- [ ] `corpus.json` with a schema version and migration path
- [ ] `curat0r verify` — walk unverified drafts, confirm or discard, one at a time
- [ ] Gap interview wired to the corpus so answers become blocks

**Exit:** ingest once, verify once, tailor many times.

## Phase 4 — output

- [ ] DOCX from a base template — port `auto_interner.corpus.assemble`
- [ ] Coverage report alongside every generated document
- [ ] Web UI for verification, which is the step most worth having a screen for

## Phase 5 — other people

Everything above is single-user. This is where it stops being a personal tool.

- [ ] Per-user corpus isolation
- [ ] Bring-your-own API tokens, never stored server-side
- [ ] Hosted demo with fictional data only

## Explicitly not planned

- **Auto-submitting applications.** Violates most portal terms and gets
  applications spam-flagged. Same reason `auto_Interner` cut it.
- **Scraping LinkedIn, Indeed or Glassdoor.** Their terms prohibit it and
  LinkedIn has litigated. The user brings that data; the guard enforces it.
- **Writing bullets for you.** The entire premise. A tool that generates a claim
  about your experience is every other résumé tool.

## Phase 1.5: absorb the corpus engine from auto_Interner

Decided 2026-08-19. The selection engine was built inside `auto_Interner` and
sits there orphaned, imported by nothing on that project's live path.

It belongs here. It is corpus-driven, source-agnostic and written for arbitrary
users, which is this project and not that one.

| moving in | |
|---|---|
| `blocks.py` | verified block corpus, evidence subsumption |
| `requirements.py` | weighted extraction, alternation groups, 119-term taxonomy |
| `selection.py` | maximum-coverage selection, structural shape rules |
| `coverage.py` | evidence scoring, honest gap reporting |
| `tagging.py` | phrase rules with provenance on every tag |
| `assemble.py` | delete-only DOCX assembly, title-line link rule |
| `formatting.py` | one-page typography fitting with floors |
| `render.py` | text rendering |
| tests | 75, currently in one file |

1,889 lines, 75 tests. The only dependency outside itself is
`auto_interner.documents.template_reader`, so exactly one thing needs porting or
reimplementing.

**Sequence matters.** Both repositories are uncommitted, and moving nineteen
hundred lines between two repositories without restore points is how a day's
work disappears. Push both first.

## Relationship to auto_Interner

`auto_Interner` is a personal pipeline: one user, one Pi, discovery through
tailoring. `Curat0r` is the corpus half generalised.

They share a **format, not a dependency** — Curat0r emits the corpus JSON that
`auto_interner.corpus` reads. Either can be rewritten without touching the other.

Phase 4 will port the template assembler across. That is a copy with attribution,
not an import.
