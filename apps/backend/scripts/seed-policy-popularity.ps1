<#+
.SYNOPSIS
최근 7일의 테스트 정책 인기도를 Redis와 policy_popularity_ranking DB 테이블에 적재합니다.

.DESCRIPTION
- Redis: 실제 서비스와 동일한 policy:popularity:view-events ZSET에 조회 이벤트를 넣습니다.
- DB: Redis 이벤트와 동일한 조회수(조회 1점, 좋아요 0건)를 상위 10개 랭킹으로 적재합니다.
- 같은 정책/일/순번의 Redis member를 재사용하므로, 기본 실행은 여러 번 실행해도 중복 적재되지 않습니다.
- 실제 좋아요는 만들지 않습니다. 좋아요는 회원 FK를 가지므로 테스트 회원 데이터를 오염시키지 않습니다.

.EXAMPLE
./scripts/seed-policy-popularity.ps1 -DbPassword '...' -RedisPassword '...'

.EXAMPLE
# 개발용 Redis 조회 이벤트를 전부 교체할 때만 사용합니다. 운영 데이터에는 사용하지 마세요.
./scripts/seed-policy-popularity.ps1 -DbPassword '...' -RedisPassword '...' -ReplaceAllViewEvents
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$DbHost = '192.168.0.176',
    [int]$DbPort = 5432,
    [string]$DbName = 'busanyouth',
    [string]$DbUser = 'busanyouth',
    [Parameter(Mandatory = $true)][string]$DbPassword,
    [string]$RedisHost = 'localhost',
    [int]$RedisPort = 6379,
    [Parameter(Mandatory = $true)][string]$RedisPassword,
    [ValidateRange(1, 10)][int]$PolicyLimit = 10,
    [ValidateRange(1, 30)][int]$Days = 7,
    [switch]$ReplaceAllViewEvents
)

$ErrorActionPreference = 'Stop'
$ViewEventsKey = 'policy:popularity:view-events'

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name 명령을 찾을 수 없습니다. PostgreSQL client(psql)와 Redis client(redis-cli)를 설치한 뒤 PATH에 추가하세요."
    }
}

Require-Command 'psql'
Require-Command 'redis-cli'

$env:PGPASSWORD = $DbPassword
$env:REDISCLI_AUTH = $RedisPassword
$connection = "postgresql://${DbUser}@${DbHost}:${DbPort}/${DbName}"

try {
    $rankingTable = (& psql --dbname=$connection --tuples-only --no-align --command "SELECT to_regclass('public.policy_popularity_ranking');").Trim()
    if ($rankingTable -ne 'policy_popularity_ranking') {
        throw 'policy_popularity_ranking 테이블이 없습니다. 백엔드를 한 번 기동해 JPA 테이블 생성을 먼저 완료하세요.'
    }

    $policyIds = @(& psql --dbname=$connection --tuples-only --no-align --command "SELECT id FROM policy WHERE plcy_aprv_stts_cd = '0044002' ORDER BY id LIMIT $PolicyLimit;" |
        Where-Object { $_ -match '^\d+$' } |
        ForEach-Object { [long]$_ })
    if ($policyIds.Count -eq 0) { throw '적재할 승인 정책이 없습니다.' }

    if ($ReplaceAllViewEvents) {
        if ($PSCmdlet.ShouldProcess($ViewEventsKey, '기존 Redis 정책 조회 이벤트 전체 삭제')) {
            & redis-cli -h $RedisHost -p $RedisPort DEL $ViewEventsKey | Out-Null
        }
    }

    $now = (Get-Date).ToUniversalTime()
    $rows = New-Object System.Collections.Generic.List[object]
    for ($policyIndex = 0; $policyIndex -lt $policyIds.Count; $policyIndex++) {
        $policyId = $policyIds[$policyIndex]
        # 앞 정책일수록 더 많은 조회를 생성해 눈으로 순위를 확인할 수 있게 한다.
        $totalViews = 0
        for ($day = 0; $day -lt $Days; $day++) {
            $dailyViews = (($policyIds.Count - $policyIndex) * 3) + ($day % 3)
            for ($eventIndex = 0; $eventIndex -lt $dailyViews; $eventIndex++) {
                $eventTime = $now.AddDays(-$day).AddMinutes(-($eventIndex * 7 + $policyIndex))
                $timestamp = [DateTimeOffset]$eventTime
                $milliseconds = $timestamp.ToUnixTimeMilliseconds()
                $member = "${policyId}:seed:${day}:${eventIndex}"
                & redis-cli -h $RedisHost -p $RedisPort ZADD $ViewEventsKey $milliseconds $member | Out-Null
                $totalViews++
            }
        }
        $rows.Add([PSCustomObject]@{ PolicyId = $policyId; Views = $totalViews; Score = $totalViews })
    }

    # 서비스와 같은 30일 윈도우 컬럼을 기록한다. 실제 스케줄러가 다음 10분 집계에서 좋아요 점수까지 다시 반영한다.
    $windowStart = $now.AddDays(-30).ToString('yyyy-MM-dd HH:mm:ss')
    $calculatedAt = $now.ToString('yyyy-MM-dd HH:mm:ss')
    for ($rank = 0; $rank -lt $rows.Count; $rank++) {
        $row = $rows[$rank]
        $rankOrder = $rank + 1
        $sql = "INSERT INTO policy_popularity_ranking (policy_id, rank_order, score, view_count_30d, like_count_30d, window_started_at, calculated_at) VALUES ($($row.PolicyId), $rankOrder, $($row.Score), $($row.Views), 0, '$windowStart', '$calculatedAt') ON CONFLICT (policy_id) DO UPDATE SET rank_order = EXCLUDED.rank_order, score = EXCLUDED.score, view_count_30d = EXCLUDED.view_count_30d, like_count_30d = EXCLUDED.like_count_30d, window_started_at = EXCLUDED.window_started_at, calculated_at = EXCLUDED.calculated_at;"
        & psql --dbname=$connection --quiet --command $sql
    }
    & psql --dbname=$connection --quiet --command "DELETE FROM policy_popularity_ranking WHERE rank_order > $($rows.Count);"
    Write-Host "완료: 최근 $Days일 조회 이벤트 $($rows.Views | Measure-Object -Sum | Select-Object -ExpandProperty Sum)건을 Redis에 적재하고, 정책 $($rows.Count)건의 DB 인기 랭킹을 갱신했습니다." -ForegroundColor Green
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:REDISCLI_AUTH -ErrorAction SilentlyContinue
}
