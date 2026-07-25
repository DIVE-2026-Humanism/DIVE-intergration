-- 개발용 공동구매 8건과 인앱 알림 4건. 첫 번째 회원에게 연결하며 중복 제목은 건너뜁니다.
INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'부산 청년 자취생 세제 대용량 공구','대용량 세제를 함께 구매해 배송비를 아껴요.',8900,5,3,'RECRUITING',NOW(),NOW()+INTERVAL '6 days','/images/gonggu-demo-bundle.png','https://example.com/products/laundry-detergent',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='부산 청년 자취생 세제 대용량 공구');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'무선 키보드·마우스 세트 공동구매','재택·스터디용 무선 키보드와 마우스 세트입니다.',24900,8,5,'RECRUITING',NOW(),NOW()+INTERVAL '5 days','/images/gonggu-demo-bundle.png','https://example.com/products/keyboard-mouse',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='무선 키보드·마우스 세트 공동구매');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'스터디 카페 20시간 이용권','서면 인근 스터디 카페 이용권을 인원 할인가로 구매합니다.',18000,10,7,'RECRUITING',NOW(),NOW()+INTERVAL '4 days','/images/gonggu-demo-bundle.png','https://example.com/products/study-cafe-pass',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='스터디 카페 20시간 이용권');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'여름 침구 냉감 패드 공구','1인 가구용 싱글 냉감 패드입니다.',21900,6,2,'RECRUITING',NOW(),NOW()+INTERVAL '3 days','/images/gonggu-demo-bundle.png','https://example.com/products/cooling-pad',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='여름 침구 냉감 패드 공구');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'텀블러·다회용 빨대 세트','출퇴근과 캠퍼스에서 쓰기 좋은 텀블러 세트 공동구매예요.',12900,7,6,'RECRUITING',NOW(),NOW()+INTERVAL '2 days','/images/gonggu-demo-bundle.png','https://example.com/products/tumbler-set',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='텀블러·다회용 빨대 세트');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'부산 로컬 원두 1kg 공구','원두 1kg을 분할 수령합니다.',17500,12,9,'RECRUITING',NOW(),NOW()+INTERVAL '5 days','/images/gonggu-demo-bundle.png','https://example.com/products/local-coffee',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='부산 로컬 원두 1kg 공구');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'자격증 교재·문제집 공구','다음 시험 회차 대비 최신 교재입니다.',15400,9,4,'RECRUITING',NOW(),NOW()+INTERVAL '7 days','/images/gonggu-demo-bundle.png','https://example.com/products/exam-book',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='자격증 교재·문제집 공구');

INSERT INTO gonggu (member_id,title,content,price,target_count,current_count,status,start_date,end_date,image_url,product_url,created_at,updated_at)
SELECT member_id,'주방 밀폐용기 12종 세트','자취생 냉장고 정리용 밀폐용기입니다.',19900,6,1,'RECRUITING',NOW(),NOW()+INTERVAL '6 days','/images/gonggu-demo-bundle.png','https://example.com/products/food-container',NOW(),NOW()
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title='주방 밀폐용기 12종 세트');

INSERT INTO notification (member_id,title,body,type,is_read,created_at)
SELECT member_id,'공동구매 마감 임박','텀블러·다회용 빨대 세트 모집 마감이 2일 남았어요.','gonggu',false,NOW()-INTERVAL '20 minutes'
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM notification WHERE title='공동구매 마감 임박');

INSERT INTO notification (member_id,title,body,type,is_read,created_at)
SELECT member_id,'새 맞춤 정책이 도착했어요','내 경제 안정성 점수를 기준으로 추천 정책 5건을 확인해보세요.','policy',false,NOW()-INTERVAL '3 hours'
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM notification WHERE title='새 맞춤 정책이 도착했어요');

INSERT INTO notification (member_id,title,body,type,is_read,created_at)
SELECT member_id,'공구 참여 현황','부산 로컬 원두 1kg 공구에 9명이 참여했어요. 목표까지 3명 남았습니다.','gonggu',false,NOW()-INTERVAL '1 day'
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM notification WHERE title='공구 참여 현황');

INSERT INTO notification (member_id,title,body,type,is_read,created_at)
SELECT member_id,'정책 즐겨찾기 안내','관심 있는 정책을 저장하면 마감 전에 다시 확인할 수 있어요.','policy',true,NOW()-INTERVAL '2 days'
FROM (SELECT member_id FROM member ORDER BY member_id LIMIT 1) m WHERE NOT EXISTS (SELECT 1 FROM notification WHERE title='정책 즐겨찾기 안내');
