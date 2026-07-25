import { api } from './http';
import { Policy, PolicyDetail } from '../types';

// 백엔드 PolicyResponse (온통청년 필드명 그대로)
type PolicyResponse = {
  id: number;
  plcyNo: string | null;
  plcyNm: string | null;
  plcyKywdNm: string | null;
  plcyExplnCn: string | null;
  plcySprtCn: string | null;
  lclsfNm: string | null;
  mclsfNm: string | null;
  sprvsnInstNm: string | null;
  aplyUrlAddr: string | null;
  aplyPrdSeCd: string | null;
  aplyYmd: string | null;
  sprtTrgtMinAge: number | null;
  sprtTrgtMaxAge: number | null;
  viewCount: number | null;
};

type PolicyDetailResponse = PolicyResponse & {
  plcyAplyMthdCn: string | null;
  srngMthdCn: string | null;
  sbmsnDcmntCn: string | null;
  sprtSclCnt: string | null;
  sprtTrgtAgeLmtYn: string | null;
  earnCndSeCd: string | null;
  earnMinAmt: string | null;
  earnMaxAmt: string | null;
  earnEtcCn: string | null;
  addAplyQlfcCndCn: string | null;
  ptcpPrpTrgtCn: string | null;
};

export type PolicyCategory = { lclsfNm: string; mclsfNms: string[] };

function text(value: string | null | undefined): string {
  return value?.trim() ?? '';
}

function targetAge(min: number | null, max: number | null): string {
  if (min && max) return `만 ${min}세 ~ ${max}세`;
  if (min) return `만 ${min}세 이상`;
  if (max) return `만 ${max}세 이하`;
  return '연령 기준 확인 필요';
}

function toPolicy(r: PolicyResponse): Policy {
  const kw = text(r.plcyKywdNm).split(',').map((s) => s.trim()).filter(Boolean).join(' · ');
  const expl = text(r.plcyExplnCn);
  const support = text(r.plcySprtCn);
  const summarySource = support || expl || kw;
  const summary = summarySource.length > 58 ? `${summarySource.slice(0, 58)}…` : summarySource;
  const deadline = text(r.aplyYmd) || '상시모집';
  return {
    id: String(r.id),
    title: r.plcyNm ?? '',
    category: r.lclsfNm ?? '기타',
    subCategory: text(r.mclsfNm),
    summary,
    benefit: support || expl || summary,
    period: deadline,
    deadline,
    days: 9999,
    popularity: r.viewCount ?? 0,
    description: expl,
    institution: text(r.sprvsnInstNm) || '주관기관 정보 없음',
    targetAge: targetAge(r.sprtTrgtMinAge, r.sprtTrgtMaxAge),
    applyUrl: text(r.aplyUrlAddr),
  };
}

function toPolicyDetail(r: PolicyDetailResponse): PolicyDetail {
  const policy = toPolicy(r);
  const income = [text(r.earnCndSeCd), text(r.earnMinAmt), text(r.earnMaxAmt), text(r.earnEtcCn)]
    .filter(Boolean)
    .join(' · ');

  return {
    ...policy,
    keywords: text(r.plcyKywdNm),
    applicationMethod: text(r.plcyAplyMthdCn),
    screeningMethod: text(r.srngMthdCn),
    documents: text(r.sbmsnDcmntCn),
    supportScale: text(r.sprtSclCnt),
    incomeCondition: income,
    additionalCondition: text(r.addAplyQlfcCndCn),
    participationRestriction: text(r.ptcpPrpTrgtCn),
  };
}

/** 전체 정책 (홈/기본). GET /api/v1/policy/all */
export async function getPolicyList(): Promise<Policy[]> {
  const list = await api<PolicyResponse[]>('/api/v1/policy/all');
  return list.map(toPolicy);
}

/** 대분류/중분류/키워드 필터링. GET /api/v1/policy/all?lclsfNm=&mclsfNm=&keyword= */
export async function getPolicies(lclsfNm?: string | null, mclsfNm?: string | null, keyword?: string | null): Promise<Policy[]> {
  const params = new URLSearchParams();
  if (lclsfNm) params.set('lclsfNm', lclsfNm);
  if (mclsfNm) params.set('mclsfNm', mclsfNm);
  if (keyword) params.set('keyword', keyword);
  const q = params.toString();
  const list = await api<PolicyResponse[]>(`/api/v1/policy/all${q ? `?${q}` : ''}`);
  return list.map(toPolicy);
}

/** 정책 상세. GET /api/v1/policy/{id} */
export async function getPolicyDetail(id: string): Promise<PolicyDetail> {
  const policy = await api<PolicyDetailResponse>(`/api/v1/policy/${id}`);
  return toPolicyDetail(policy);
}

/** 대분류+중분류 목록 (필터 UI). GET /api/v1/policy/categories */
export function getPolicyCategories(): Promise<PolicyCategory[]> {
  return api<PolicyCategory[]>('/api/v1/policy/categories');
}

/** 좋아요(관심) 토글 — 이미 눌렀으면 취소. POST /api/v1/policy/{id} (로그인 필요) */
export function togglePolicyLike(id: string): Promise<void> {
  return api<void>(`/api/v1/policy/${id}`, { method: 'POST', auth: true });
}

/** 내가 좋아요한 정책 목록. GET /api/v1/policy/myLike (로그인 필요) */
export async function getMyLikedPolicies(): Promise<Policy[]> {
  const list = await api<PolicyResponse[]>('/api/v1/policy/myLike', { auth: true });
  return list.map(toPolicy);
}

/** 실시간 인기 Top10 정책 ID. GET /api/v1/policy/topPolicies (policyId 배열 반환) */
export async function getTopPolicies(): Promise<number[]> {
  return api<number[]>('/api/v1/policy/topPolicies');
}
