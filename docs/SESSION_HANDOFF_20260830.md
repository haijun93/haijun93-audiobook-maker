# Session Handoff — 2026-08-30

## Completed

- Confirmed the `Dark City - Frank Lauria` leak: legacy cache responses for the copyright, dedication, quote, and prologue blocks were accepted because frontmatter metadata was excluded from the old translation-quality gate.
- Added a strict untranslated-output gate. Missing or English-only prose now blocks chunk cache acceptance and EPUB publication; the old `[번역 누락] + English` fallback was removed.
- Added strict `[k]` derivation preflight so an incomplete `[k-e]` source cannot produce a Korean-only EPUB.
- Added the shared zero-X-Ray policy in `audiobook_studio/epub_xray_policy.py`; it removes dossier members and OPF/nav/NCX references, including `dramatis-personae` filename variants.
- Updated publishers, rebuilders, healers, and legacy “X-Ray” scripts to obey the zero-X-Ray policy.
- Local `소설2` purge completed: 7,277 EPUBs inspected, 29 X-Ray artifacts/references removed; post-scan found no X-Ray residue in valid EPUBs. One unrelated non-ZIP file remains separately corrupted.
- Fixed two regression issues found by tests: XML entity declarations are no longer swallowed by the permissive parser fallback, and `[study]Some Book.epub` preserves its no-space prefix form.
- Re-enabled the idle ChatGPT worker by removing `.work/chatgpt_disabled.flag`; the supervisor dispatched `The Round House - Louise Erdrich (3.65)`.
- Fixed supervisor dispatch failures caused by an undefined `_CONFIG_CACHE`, and made forced retranslation tasks bypass the stale “chunk file count is complete” shortcut.
- Removed the obsolete whole-library X-Ray injector from the 30-minute health
  report; it only caused a costly rescan under the zero-X-Ray policy.
- Added `scripts/ensure_missing_english_originals.py`. It detects translated
  books without a matching `[e]` source, normalizes rating/author suffixes,
  uses the integrated OceanofPDF -> Readrobe fallback, validates downloads,
  and registers verified files as Stage-2 tasks.
- Added `scripts/sync_original_toc_across_library.py`. Matching editions now
  have an explicit tool to copy the original `[e]` `nav.xhtml`/NCX structure;
  it never invents synthetic `제N막` entries and supports dry-run/`--apply`.

## In progress

- `Dark City` strict repair is queued at priority 5000 in `.work/continuous_scheduler/config.json`, reusing `_translation_work_stage1_vk_darkcityfranklauria`. It will be assigned to the next available worker and must pass the strict gate before rebuilding `[k-e]`, `[study]`, and `[k]`.
- Current workers at handoff: Sentence, Master Butchers Singing Club, LaRose, and The Round House; all were reporting fresh heartbeats.
- Google Drive full-library purge was attempted but stopped after all 16 processes remained blocked on synced-volume I/O. The five Google Drive `Dark City` copies were checked individually and were X-Ray-free. The purge script now supports `--library-root` for a later retry.
- Original EPUB recovery discovery found 234 candidates. The first recovery
  run successfully added `Stay Close`, `Just One Look`, `Long Lost`, and `The
  Bone Maker`; `Precious Blood` and `A Hard Death` had no verified download.
  The recovery command is resumable and skips existing originals.
- Worker continuity repair is active. The supervisor now honors explicit
  `status=completed` before legacy `retrans_` heuristics, preventing the
  completed Dark City task from being relaunched. Child failures are tracked
  by task ID; failed tasks receive 15/30/60-minute backoff and are quarantined
  after three failures so a malformed AI response cannot monopolize a worker.
- `scripts/capture_all_workers_visual_state.py` now discovers all four live
  worker processes dynamically, reads their current work directories and
  heartbeats, copies any Playwright `latest_screenshot.png`, and records a
  visible macOS display fallback at `.work/continuous_scheduler/screenshots/`.
  A watch monitor is running alongside the supervisor.
- At the latest audit, workers 1–3 were running Gemini tasks and worker 4 was
  in ChatGPT pacing/rate-limit recovery. The strict `untranslated_output`
  failures remain intentionally rejected and are now isolated with backoff;
  the quality gate was not weakened.
- Fixed a Tier-3 false positive where `001-back-cover.xhtml` was mistaken for
  the front cover; Dark City `[study]` now passes 15-page visual rendering
  with zero blank/broken pages. Worker-page capture is now invoked for both
  the normal prepared-page path and retry/error paths, with capture failures
  written to `screenshot_errors.jsonl`.
- Corrected the earlier Dark City `[k]` handoff error: the real file was an
  older Aug-29 artifact containing 34 English-only paragraphs, duplicate TOC
  entries, and three broken OPF references. The converter previously wrote
  beside `[k-e]` instead of mirroring into the standard `[k]` root. It now
  mirrors the edition root, translates standalone structural labels, and the
  corrected `[k]` file was rebuilt from the current `[k-e]` source on Aug 30.
  Tier-1, Tier-2, and Tier-3 now all pass for the actual library path.
- Fixed the Dark City Xteink omission: `[xteink]/[study_x]` and
  `[xteink]/[e-s_x]` existed only as stale Aug-29 copies because the dedicated
  builder was not connected to the live translation workflow. Added the
  incremental `build_xteink_book_pair()` API, centralized canonical
  destinations, and hooked it into `webui/workflow_runner.py`; the all-edition
  healer now rebuilds both dedicated Xteink layouts instead of the obsolete
  `[xteink]/[e-s]` path. Dark City `[e-s]`, `[study_x]`, and `[e-s_x]` were
  regenerated from the current `[study]`/`[e-s]` sources.

## Verification

- `.venv311/bin/python -m pytest -q tests/test_translation_quality_pipeline.py tests/test_epub_integrity.py` → `106 passed`.
- Full suite: `437 passed, 8 unrelated pre-existing failures` in ChatGPT page mocks, book organizer behavior, and partial web-app batch organization.
- All edited Python files compiled successfully with `.venv311/bin/python -m py_compile`.
- Focused scheduler/translation/integrity tests after the operational fixes →
  `126 passed`; Ruff checks passed for the new recovery and TOC tools.
- Xteink repair verification: `.venv311/bin/python -m pytest -q
  tests/test_translation_quality_pipeline.py tests/test_epub_integrity.py
  tests/test_web_workflow_runner.py` → `128 passed`; modified Xteink/workflow
  modules compile and pass Ruff. Dark City `[k-e]`, `[study]`, `[e-s]`, `[k]`,
  `[study_x]`, and `[e-s_x]` each pass Tier-1/Tier-2/Tier-3 (15 rendered
  pages, zero blank/broken resources, zero X-Ray residue).
- Repaired `Presumed Innocent - Scott Turow` after confirming that the source
  `[e]` itself had only a generic `Start` NCX entry and no EPUB3 `nav.xhtml`.
  After the user supplied the retail TOC, the source and all six derived
  editions now expose the exact 53-point hierarchy: Cover, Title Page,
  Copyright, Dedication, Opening Statement; `SPRING` (Chapters 1–17),
  `SUMMER` (Chapters 18–36), `FALL` (Chapters 37–40); Closing Argument and
  the four supplied backmatter labels. Each numbered entry points to the
  actual first prose paragraph after its source numeric marker, not merely to
  the beginning of a split file. The old synthetic `1장`–`11장` wrappers were
  removed, and `[k]` uses Korean labels while bilingual editions retain
  English/Korean labels.
- Root cause fixed in the translation pipeline: when an EPUB supplied only a
  generic `Start`/`Begin` entry, the splitter could expand unreferenced spine
  gaps into fake `Chapter N` sections. It now recovers non-numeric h1–h3
  headings from the source and disables that fallback expansion for recovered
  navigation. The source-specific repair is idempotent and also repairs the
  previously observed ruby/XML defects in the six generated editions.
- Cleaned `Presumed Innocent`'s Summer indictment block in the source and all
  six generated editions: removed OCR/table-only `)` rows and `[번역 누락]`,
  restored `RUSTY K. SABICH` from the source's broken placeholder-image text,
  corrected `A TRUE BILL`, `Revised State Statutes`, and the Korean legal
  labels, while retaining the actual indictment prose and signatures. The
  exact `[k]` file was rechecked by all three inspectors after this content
  repair.
- Follow-up repair completed for those six malformed ruby-tag files in
  `Presumed Innocent`: the targeted XML sanitizer repaired only malformed
  chapter XHTML atomically, preserved the text content, and rebuilt both
  Xteink editions from the healed `[study]`/`[e-s]` sources. All six derived
  editions now have zero XML parse errors, zero broken TOC links, and pass
  Tier-1/Tier-2/Tier-3 (13 rendered pages each).
- Added a regression test for a generic `Start` NCX with semantic in-body
  headings; the focused suite now passes `129 tests`.
- Restored the source copyright line omitted by the earlier translator,
  created valid destinations for the supplied promotional backmatter labels,
  and made the root-layout `[e]` cover page render its packaged cover image.
  The Summer indictment cleanup remains active: OCR-only parentheses and
  `[번역 누락]` markers are absent, and the repaired legal names/labels remain
  in all derived editions.
- Final verification after the exact retail TOC update: all six generated
  editions pass Tier-1 and Tier-2 with 53 NCX points and zero broken package or
  TOC links; all six pass Tier-3 with 13 rendered pages and zero visual flaws.
  The root-layout `[e]` source was independently checked with 53 nav/NCX
  points, zero broken links, valid XML, and a 27,481-byte cover image.
- Added visible chapter-start labels to the book body itself. The root `[e]`
  source now displays `Chapter 1` through `Chapter 40` at the original numeric
  boundaries; `[k]` displays `1장` through `40장`; bilingual editions display
  both forms. The existing TOC fragments were moved onto these visible
  headings, so selecting a chapter lands on the label and its opening prose.
  All seven editions contain exactly 40 visible chapter markers and the repair
  remains idempotent.

## Whole-library maintenance run (2026-08-30)

- Audited the library inventory: 7,317 EPUBs at the start of the run; the
  active translation workers and visual monitor were left running.
- Applied the global zero-X-Ray purge to 7,294 EPUBs initially and 7,561 on a
  later pass; no X-Ray artifacts remained and no book files were deleted.
- Applied the safe XML/control-character, scene-subheading, and mimetype
  healer; 26 EPUBs required those repairs.
- Synchronized original `[e]` navigation to matching editions where links
  were valid: 3,078 matches, 474 rewritten, 2,604 already clean or safely
  skipped. The synchronizer now isolates `zlib.error`/bad-archive files
  instead of aborting the entire run.
- Rebuilt valid derived editions: 319 `[k]` from `[k-e]`, 319 `[e-s]` from
  `[study]`, and 1,102 Xteink editions (569 `[study_x]`, 533 `[e-s_x]`).
- The final archive scan found 972 unresolved invalid EPUB archives:
  `[xteink]` 356, `[e-s]` 178, `[study]` 172, `[k]` 140, `[k-e]` 121,
  backup 4, and `[e]` 1. These are not silently marked complete: most are
  damaged source archives or source books with untranslated blocks/broken
  fragments and require source recovery or retranslation before regeneration.
- The existing fast `[k]` content audit identified 93 books with likely
  untranslated paragraphs and 49 with suspicious numeric TOC sequences; the
  numeric check includes known duplicate-link false positives and is not a
  final semantic TOC verdict.

## Immediate recovery dispatch (2026-08-30)

- The residual-recovery queue was not previously active: its configuration had
  zero priority-10000 tasks and the invalid-archive recovery report was a dry
  run. This was corrected immediately.
- The deterministic derived-edition repair pass examined 1,123 targets and
  found no valid local source archive to copy; it therefore made no unsafe
  blind replacements. Those cases are now routed through source retranslation.
- The source/retranslation prioritizer identified 346 damaged source tasks and
  registered 316 with `priority=10000`, `stage=0`, and
  `force_retranslate=true`, ahead of all new work.
- The supervisor was restarted with short-lived worker registration fixed so
  failed dispatches enter retry backoff/quarantine instead of being relaunched
  in a tight loop. Four workers are active; the first recovery task is
  `Butcher Blackbird 40 The Ruinou Brynne Weaver` on the main Gemini worker.
- This is an active recovery run, not a completion claim: the remaining
  archives, suspected untranslated books, and TOC candidates will be cleared
  as the prioritized tasks finish and pass the quality gates.
