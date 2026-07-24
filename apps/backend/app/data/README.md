# KCB 샘플 데이터

`kcb_samples.json`은 정밀 진단(`mode: "precise"`)에서 `sampleId`로 조회하는 KCB 43필드
레코드 모음이다. `services/kcb_samples.py`가 여기서 로드한다.

## 출처

`sample-01`은 실제 개인 KCB 데이터가 아니라, `meeting/integration_guide.md`(모델팀이
외부 연동 테스트용으로 공개한 계약 문서)의 "정밀 진단 입력" 예시에 있던 값을 그대로
옮긴 것이다. 팀 확인 완료 — 그대로 사용해도 되는 샘플.

추가 페르소나가 필요하면 같은 형식으로 `sample-02` 등을 더 추가하면 된다. 필드명은
`/v1/meta`의 `precise_input.required_kcb_columns`와 공백까지 정확히 일치해야 한다.
