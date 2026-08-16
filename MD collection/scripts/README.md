# scripts/ 작업절차 문서 색인

저장소 `scripts/` 폴더의 실행 가능한 스크립트 51개 전부를 한 파일씩 문서화한 목록. 다른 AI/사람이 이어받아 작업할 수 있도록, 각 스크립트가 "무엇을 위한 것인지·어떻게 실행하는지·다른 스크립트와 어떻게 연결되는지"를 기록했다. (임포트만 되고 직접 실행하지 않는 순수 라이브러리 모듈 `atomic_io.py`, `book_cover_lookup.py`, `epub_integrity.py`, `safe_xml.py`, `translation_quality_checks.py`, `__init__.py`는 별도 문서 없이 제외했다 — 이들은 위 문서들 안에서 필요할 때 언급된다.)

저장소 루트: `/Users/hyeokjunkong/Desktop/myproject_python/haijun93-audiobook-maker`

## 1. EPUB 번역 핵심 파이프라인 (지금 실제로 돌아가는 경로)

웹 UI(`web_app.py`)가 배치를 시작하면 `webui/workflow_runner.py`가 아래 순서로 스크립트들을 호출한다.

- [translate_epub_with_chatgpt_web_to_study_epub.py](translate_epub_with_chatgpt_web_to_study_epub.md) — 핵심 번역 엔진
- [make_korean_only_epubs.py](make_korean_only_epubs.md) — `[k-e]`→`[k]` 파생
- [final_epub_tone_review.py](final_epub_tone_review.md) / [final_epub_dialogue_consistency_review.py](final_epub_dialogue_consistency_review.md) — 자동 호출되는 톤/대화 2종 검수
- [final_epub_literary_review.py](final_epub_literary_review.md) / [final_epub_quality_audit.py](final_epub_quality_audit.md) — 수동 보조 검수(자동 호출 아님)
- [export_pdf_to_kindle_epub.py](export_pdf_to_kindle_epub.md) — PDF 원서를 번역 전 EPUB으로 변환(배치가 내부적으로 재사용)

중복 번역 방지 절차와 검증기 오탐 예외 규칙은 이 폴더 상위(`MD collection/`)의 별도 절차 문서 참고:
- [EPUB 배치 번역 중복작업 방지 처리절차](../EPUB%20배치%20번역%20중복작업%20방지%20처리절차.md)
- [EPUB 번역 품질 검증기 오탐 예외 처리 규칙](../EPUB%20번역%20품질%20검증기%20오탐%20예외%20처리%20규칙.md)
- [EPUB 대화체(말투) 검수 작업지시서](../EPUB%20대화체(말투)%20검수%20작업지시서.md)

## 2. 레거시/대안 배치 실행 경로 (CLI 전용, 지금 웹 UI가 쓰지 않음)

- [run_soseol2_chatgpt_k_e_batch.py](run_soseol2_chatgpt_k_e_batch.md) — `소설2` 전체용 CLI 배치(분류·검수·유휴유지보수까지 연동)
- [run_k_e_batch_with_shutdown.py](run_k_e_batch_with_shutdown.md) — 더 이전 세대, 구 서재(`소설/#books_source`) 대상
- [idle_completed_epub_tone_maintenance.py](idle_completed_epub_tone_maintenance.md) — 유휴 시간에 완료된 책들을 재점검·안전 교정
- [monitor_chatgpt_web_ox_batch.py](monitor_chatgpt_web_ox_batch.md) — (공무원 시험 OX 배치용 watchdog, 아래 6번 참고)
- [run_followup_chatgpt_web_jobs.py](run_followup_chatgpt_web_jobs.md) — 범용 "하나 끝나면 다음" 대기열

## 3. EPUB 정리·무결성·중복제거·서지

- [dedupe_against_finished.py](dedupe_against_finished.md) — 수동 중복 사전 정리(배치가 자동으로도 함)
- [classify_soseol2_epubs_by_category.py](classify_soseol2_epubs_by_category.md) — 장르 분류·이동
- [remove_readrobe_text_from_epubs.py](remove_readrobe_text_from_epubs.md) — 워터마크 제거(공용 함수, 여러 스크립트가 재사용)
- [ensure_missing_epub_covers.py](ensure_missing_epub_covers.md) / [replace_generated_epub_covers_with_online.py](replace_generated_epub_covers_with_online.md) — 표지 채우기/교체
- [audit_translated_epubs.py](audit_translated_epubs.md) / [extract_epub_review_samples.py](extract_epub_review_samples.md) — 구 서재 전용 감사·표본 추출
- [convert_artemis_inline_to_span.py](convert_artemis_inline_to_span.md) — 책 한 권 형식 마이그레이션(일회성)

## 4. 책별 수동 말투 교정 (honorifics)

- [refine_artemis_honorifics.py](refine_artemis_honorifics.md), [refine_corrupt_honorifics.py](refine_corrupt_honorifics.md), [refine_dark_notes_honorifics.py](refine_dark_notes_honorifics.md) — 하드코딩 치환 목록 패턴
- [refine_better_than_the_movies_final.py](refine_better_than_the_movies_final.md) — 사람이 먼저 문맥 검토 후 반영
- [refine_lessons_in_sin_honorifics.py](refine_lessons_in_sin_honorifics.md) — Gemini 웹으로 검토 자체를 자동화

## 5. PDF/DOCX 리더 기기용 내보내기 (공무원 시험 학습자료 전용)

- [prepare_docx_for_reader_exports.py](prepare_docx_for_reader_exports.md) → [optimize_pdfs_for_kindle_scribe.py](optimize_pdfs_for_kindle_scribe.md) → [export_docx_to_pdf_epub.py](export_docx_to_pdf_epub.md) 순서
- [optimize_docx_for_a4_booklet.py](optimize_docx_for_a4_booklet.md) — 인쇄용 별도 경로

## 6. 공무원 시험(1차) OX 학습자료 가공 파이프라인

과목: 민법 / 노동법 / 사회보험법 / 경영학, 대상 폴더 `~/Desktop/1차 시험/#STD/260416`.

- 1차 보강: [enhance_civil_v1_doc.py](enhance_civil_v1_doc.md), [enhance_management_v1_doc.py](enhance_management_v1_doc.md), [enhance_social_insurance_v1_doc.py](enhance_social_insurance_v1_doc.md), [enhance_labor_ox_updated_doc.py](enhance_labor_ox_updated_doc.md)(가장 발전된 버전), [enhance_social_civil_management_docs.py](enhance_social_civil_management_docs.md)(통합 실행)
- 후속 보강: [enhance_other_subject_x_explanations.py](enhance_other_subject_x_explanations.md), [enhance_social_insurance_x_explanations.py](enhance_social_insurance_x_explanations.md)
- 이력 참조/중복 정리: [replace_explanations_from_previous_docs.py](replace_explanations_from_previous_docs.md), [group_shared_explanations.py](group_shared_explanations.md), [trim_redundant_learning_content.py](trim_redundant_learning_content.md)
- 자유형식 분석 반영: [apply_deep_analysis_results.py](apply_deep_analysis_results.md) (← [analyze_document_with_chatgpt_web.py](analyze_document_with_chatgpt_web.md) / [analyze_document_with_web_services.py](analyze_document_with_web_services.md)의 분석 결과를 반영)
- 학습 계획/체크시트: [build_35day_first_exam_master_guide.py](build_35day_first_exam_master_guide.md) → [prepend_memory_study_check_sheet.py](prepend_memory_study_check_sheet.md)
- 배치 감시: [monitor_chatgpt_web_ox_batch.py](monitor_chatgpt_web_ox_batch.md)

## 7. 범용 문서 분석 (웹 LLM)

- [analyze_document_with_chatgpt_web.py](analyze_document_with_chatgpt_web.md) — ChatGPT 웹 단일 분석
- [analyze_document_with_web_services.py](analyze_document_with_web_services.md) — ChatGPT→Claude→Gemini 심화 분석

## 8. TED/Yale 영어 학습 EPUB 빌더 (소설 번역과 무관한 별도 도메인)

- [build_ted_link_learning_epub.py](build_ted_link_learning_epub.md) — 요약/어휘 중심(대본 번역 아님)
- [build_ted_transcript_study_epub.py](build_ted_transcript_study_epub.md) → [build_ted_sentence_inline_study_epub.py](build_ted_sentence_inline_study_epub.md) — 대본 기반, 후자가 전자의 로직 재사용
- [build_yale_oyc_sentence_inline_epub.py](build_yale_oyc_sentence_inline_epub.md)(강의 1개) → [build_yale_oyc_game_theory_course_epub.py](build_yale_oyc_game_theory_course_epub.md)(코스 1개, 기반 모듈) → [build_yale_oyc_all_courses_epubs.py](build_yale_oyc_all_courses_epubs.md)(OYC 전체 코스)

## 9. 저장소 전체 점검

- [quality_gate.py](quality_gate.md) — pip check / ruff / compileall / zsh 문법 / pytest / git 공백 검사를 한 번에

---

이 색인과 개별 문서들은 **작업절차가 개선될 때마다 해당 스크립트의 md 파일을 함께 갱신**하는 규칙으로 관리한다. 새 스크립트가 추가되면 이 색인에도 항목을 추가한다.
