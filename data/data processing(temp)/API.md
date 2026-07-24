정책 불러오는 API : 04327945-efdb-472e-a4d4-4dd50543e7e6



## 해당 sector에서는 API를 호출하여 정책을 가져오고 전처리하는 데이터 프로세싱 파이프라인을 구성함
온통청년 API ──fetch──▶ raw(534) ──preprocess──▶ clean(175) ──export──▶ AI 서버 DB
                                    (마감필터+정규화)         (서버 스키마)