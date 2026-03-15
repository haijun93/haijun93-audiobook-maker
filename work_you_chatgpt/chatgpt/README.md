# ChatGPT Voice 수동 오디오북 작업 폴더

- ChatGPT URL: https://chatgpt.com/
- 권장 브라우저: Google Chrome
- 모드: advanced_voice
- 선호 음성: Spruce
- 세그먼트 수: 245
- 최종 출력 파일: audiobooks/You_Caroline_Kepnes_ko_chatgpt.m4a
- 세그먼트 텍스트: work_you_chatgpt/chatgpt/segments
- 복사용 프롬프트: work_you_chatgpt/chatgpt/prompts
- 저장할 오디오 폴더: work_you_chatgpt/chatgpt/downloads

진행 순서:
1. Chrome에서 chatgpt.com 을 엽니다.
2. Voice 설정에서 원하는 음성을 고르고, 필요하면 Advanced Voice Mode 또는 Read Aloud 흐름을 엽니다.
3. prompts 폴더의 `001_prompt.txt`부터 순서대로 붙여넣습니다.
4. 저장한 세그먼트 오디오는 `001.m4a`, `002.m4a` 같은 번호 기반 파일명으로 downloads 폴더에 넣습니다.
5. 모든 세그먼트를 저장한 뒤 같은 명령을 다시 실행하면 이 프로젝트가 최종 오디오북 파일을 자동으로 합칩니다.

주의:
- OpenAI 공식 문서는 ChatGPT Voice 사용은 안내하지만, 웹에서 완성 음성을 직접 파일로 내려받는 표준 절차는 별도로 문서화하지 않습니다.
- 따라서 이 provider는 브라우저 확장, 화면/오디오 캡처, 수동 저장 등 사용자의 로컬 워크플로우를 전제로 합니다.
- 이 프로젝트는 ChatGPT 내부 네트워크 요청을 스크래핑하지 않습니다.
