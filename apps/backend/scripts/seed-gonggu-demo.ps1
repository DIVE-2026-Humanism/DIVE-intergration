<#+
.SYNOPSIS
개발 DB에 공동구매 8건과 인앱 알림 예시를 멱등적으로 추가합니다.

.DESCRIPTION
- 회원을 지정하지 않으면 가장 먼저 생성된 회원에게 공구와 알림을 연결합니다.
- 같은 제목의 공구/같은 제목의 알림이 있으면 다시 만들지 않습니다.
- 이미지 URL은 외부 상품 예시 이미지입니다. 실제 등록 화면에서는 파일 업로드로 상품 이미지를 저장합니다.

.EXAMPLE
./scripts/seed-gonggu-demo.ps1 -DbPassword '...'

.EXAMPLE
./scripts/seed-gonggu-demo.ps1 -DbPassword '...' -MemberId 2
#>
[CmdletBinding()]
param(
    [string]$DbHost = '192.168.0.176',
    [int]$DbPort = 5432,
    [string]$DbName = 'busanyouth',
    [string]$DbUser = 'busanyouth',
    [Parameter(Mandatory = $true)][string]$DbPassword,
    [long]$MemberId = 0
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    throw 'psql 명령을 찾을 수 없습니다. PostgreSQL client를 설치한 뒤 PATH에 추가하세요.'
}

$env:PGPASSWORD = $DbPassword
$connection = "postgresql://${DbUser}@${DbHost}:${DbPort}/${DbName}"

try {
    if ($MemberId -le 0) {
        $MemberId = [long]((& psql --dbname=$connection --tuples-only --no-align --command 'SELECT member_id FROM member ORDER BY member_id LIMIT 1;').Trim())
    }
    if ($MemberId -le 0) { throw '공동구매를 등록할 회원이 없습니다. 먼저 회원을 하나 생성하거나 -MemberId를 지정하세요.' }

    $memberExists = (& psql --dbname=$connection --tuples-only --no-align --command "SELECT EXISTS (SELECT 1 FROM member WHERE member_id = $MemberId);").Trim()
    if ($memberExists -ne 't') { throw "member_id=$MemberId 회원이 없습니다." }

    $sql = @"
INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '부산 청년 자취생 세제 대용량 공구', '대용량 세제를 함께 구매해 배송비를 아껴요. 결제 후 공동구매 마감일까지 참여자를 모읍니다.', 8900, 5, 3, 'RECRUITING', NOW(), NOW() + INTERVAL '6 days', 'https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/laundry-detergent', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '부산 청년 자취생 세제 대용량 공구');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '무선 키보드·마우스 세트 공동구매', '재택·스터디용 무선 키보드와 마우스 세트입니다. 색상은 참여자 모집 후 안내해요.', 24900, 8, 5, 'RECRUITING', NOW(), NOW() + INTERVAL '5 days', 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/keyboard-mouse', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '무선 키보드·마우스 세트 공동구매');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '스터디 카페 20시간 이용권', '서면 인근 스터디 카페 이용권을 인원 할인가로 구매합니다.', 18000, 10, 7, 'RECRUITING', NOW(), NOW() + INTERVAL '4 days', 'https://images.unsplash.com/photo-1498243691581-b145c3f54a5a?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/study-cafe-pass', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '스터디 카페 20시간 이용권');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '여름 침구 냉감 패드 공구', '1인 가구용 싱글 냉감 패드입니다. 배송지는 개별 입력으로 받아요.', 21900, 6, 2, 'RECRUITING', NOW(), NOW() + INTERVAL '3 days', 'https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/cooling-pad', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '여름 침구 냉감 패드 공구');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '텀블러·다회용 빨대 세트', '출퇴근과 캠퍼스에서 쓰기 좋은 텀블러 세트 공동구매예요.', 12900, 7, 6, 'RECRUITING', NOW(), NOW() + INTERVAL '2 days', 'https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/tumbler-set', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '텀블러·다회용 빨대 세트');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '부산 로컬 원두 1kg 공구', '원두 1kg을 분할 수령합니다. 드립·에스프레소 분쇄 여부를 댓글로 알려주세요.', 17500, 12, 9, 'RECRUITING', NOW(), NOW() + INTERVAL '5 days', 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/local-coffee', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '부산 로컬 원두 1kg 공구');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '자격증 교재·문제집 공구', '다음 시험 회차 대비 최신 교재입니다. 과목별 수요가 모이면 주문합니다.', 15400, 9, 4, 'RECRUITING', NOW(), NOW() + INTERVAL '7 days', 'https://images.unsplash.com/photo-1495446815901-a7297e633e8d?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/exam-book', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '자격증 교재·문제집 공구');

INSERT INTO gonggu (member_id, title, content, price, target_count, current_count, status, start_date, end_date, image_url, product_url, created_at, updated_at)
SELECT $MemberId, '주방 밀폐용기 12종 세트', '자취생 냉장고 정리용 밀폐용기입니다. 목표 인원이 모이면 바로 주문해요.', 19900, 6, 1, 'RECRUITING', NOW(), NOW() + INTERVAL '6 days', 'https://images.unsplash.com/photo-1584990347449-a02d88f5c273?auto=format&fit=crop&w=1000&q=80', 'https://example.com/products/food-container', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM gonggu WHERE title = '주방 밀폐용기 12종 세트');

INSERT INTO notification (member_id, title, body, type, is_read, created_at)
SELECT $MemberId, '공동구매 마감 임박', '텀블러·다회용 빨대 세트 모집 마감이 2일 남았어요.', 'gonggu', false, NOW() - INTERVAL '20 minutes'
WHERE NOT EXISTS (SELECT 1 FROM notification WHERE member_id = $MemberId AND title = '공동구매 마감 임박');

INSERT INTO notification (member_id, title, body, type, is_read, created_at)
SELECT $MemberId, '새 맞춤 정책이 도착했어요', '내 경제 안정성 점수를 기준으로 추천 정책 5건을 확인해보세요.', 'policy', false, NOW() - INTERVAL '3 hours'
WHERE NOT EXISTS (SELECT 1 FROM notification WHERE member_id = $MemberId AND title = '새 맞춤 정책이 도착했어요');

INSERT INTO notification (member_id, title, body, type, is_read, created_at)
SELECT $MemberId, '공구 참여 현황', '부산 로컬 원두 1kg 공구에 9명이 참여했어요. 목표까지 3명 남았습니다.', 'gonggu', false, NOW() - INTERVAL '1 day'
WHERE NOT EXISTS (SELECT 1 FROM notification WHERE member_id = $MemberId AND title = '공구 참여 현황');

INSERT INTO notification (member_id, title, body, type, is_read, created_at)
SELECT $MemberId, '정책 즐겨찾기 안내', '관심 있는 정책을 저장하면 마감 전에 다시 확인할 수 있어요.', 'policy', true, NOW() - INTERVAL '2 days'
WHERE NOT EXISTS (SELECT 1 FROM notification WHERE member_id = $MemberId AND title = '정책 즐겨찾기 안내');
"@
    & psql --dbname=$connection --quiet --command $sql
    Write-Host "완료: member_id=$MemberId 에 공동구매 8건과 인앱 알림 4건을 준비했습니다. 같은 제목은 중복 생성하지 않습니다." -ForegroundColor Green
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
