# Translation Quality Pipeline

This document defines when a translated EPUB may be treated as complete.

## 1. Source intake

- Read the EPUB spine in reading order and preserve every source block with a stable ID.
- Record source, section, block, and chunk counts in `manifest.json`.
- Keep the original English title and author metadata.
- Reuse the original cover when available and build both EPUB navigation formats.

## 2. Character and speech guide

- Sample dialogue and narration across the beginning, middle, and ending of the whole book.
- Identify characters, relationships, hierarchy, intimacy changes, titles, and address terms.
- Define directional speech rules such as `A -> B`, including when a relationship change permits a tone change.
- Version the guide so an older beginning-only sample is not silently reused.

## 3. Context-aware draft translation

- Translate each stable source ID exactly once.
- Include nearby source blocks as read-only context for speaker, pronoun, and scene continuity.
- Keep narration and inner monologue in literary Korean `~다` style unless the source clearly requires another voice.
- Apply honorifics only to spoken dialogue and according to the relationship guide.
- Preserve negation, causality, numbers, time, names, and reference targets.
- Keep the ordinary translation prompt neutral. Add sensitive-context instructions only when the current source chunk requires them.
- Return service-limit errors to the batch immediately so cooldown time can be used for completed-book review.
- Pace consecutive web requests and limit conversation reuse to reduce transient UI and unusual-activity failures.

## 4. Per-chunk automatic validation

Before a translation chunk is cached, reject and retry it when any of these is found:

- missing or blank IDs;
- source prose copied without Korean translation;
- ChatGPT refusal or service text embedded as content;
- severe truncation relative to the source;
- one long translation repeated for multiple distinct source blocks.

Record softer review candidates such as unusual length ratios, missing numbers, or lost dialogue quotation marks without automatically rewriting valid literary choices.

## 5. EPUB construction

- Build `[k-e]` with paired `.pair`, `.ko`, and `.en` blocks.
- Derive `[k]` from the verified `[k-e]` output and remove every English study block.
- Preserve table of contents, cover, metadata, reading order, and valid XML.

## 6. Final reviews

- Run dialogue pass 1 for relationship-guide-based honorifics, endings, and narration tone.
- Run an independent dialogue pass 2 for local register continuity, casual-pronoun/polite-ending conflicts, and honorific/casual-ending conflicts.
- Compare every source block ID with the translation cache.
- Check EPUB structure, paired block counts, TOC, refusal residue, missing markers, unwanted site text, and translation-quality findings.
- Keep tone candidates and source/target anomalies in timestamped reports for later maintenance.

## 7. Completion gate

- A source EPUB moves to `finished` only after both output variants pass the final quality audit.
- A failed output is moved to `quality_gate_backups`; the source remains in the queue.
- On the next pass, outdated or suspicious cached chunks are translated again under the current pipeline version.
- A completed output may still carry non-blocking review warnings, but it cannot carry a structural error, missing source ID, refusal text, or a high-confidence untranslated/truncated block.
- Both independent dialogue review reports must exist before the quality gate can pass.

## 8. Operational safety

- Hold an exclusive batch lock and a per-book translation lock to prevent concurrent writers.
- Write JSON, reports, and EPUB outputs through temporary files followed by atomic replacement.
- Treat only canonical `chunk_NNNN.json` files as authoritative translation cache entries.
