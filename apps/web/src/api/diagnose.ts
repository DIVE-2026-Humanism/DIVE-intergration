import { api } from './http';

// 백엔드 RecommendedPolicy 계약
export type RecommendedPolicy = {
  policyId: number;
  plcyNo: string;
  plcyNm: string;
  lclsfNm: string;
  benefit: string;
  reason: string;
  caution: string;
  liked: boolean;
};

// 백엔드 DiagnoseResponse 계약
export type DiagnoseResult = {
  creditScore: number; // composite_stability_score (0~100)
  userType: 'VULNERABLE' | 'STABLE';
  typeLabel: string;
  aiReport: AiEconomicReport | null;
  recommendations: RecommendedPolicy[];
};

export type RecommendationProgress = {
  stage: 'IDLE' | 'SCORING' | 'POLICY_RECOMMENDING' | 'REPORT_GENERATING' | 'COMPLETED' | 'FAILED';
  message: string;
  percent: number;
  completed: boolean;
};

export type AiEconomicReport = {
  compositeStabilityScore: number;
  economicType: string;
  economicTypeName: string;
  majorClass: string;
  typeConfidence: number | null;
  modelVersion: string;
  feedbackMethod: 'local_llm' | 'rule_fallback' | string;
  summary: string;
  peerComparisons: { metric: string; userValue: number | null; peerAverage: number | null; gapPercent: number | null; direction: string; unit: string; source: string }[];
  housingBenchmark: { region: string; monthlyRentMedian: number | null; monthlyDepositMedian: number | null; jeonseDepositMedian: number | null; period: string; source: string; notice: string } | null;
  feedback: { category: string; message: string; evidence: string }[];
  guides: { priority: number | null; title: string; action: string }[];
  disclaimer: string;
  sources: string[];
};

export type SavedRecommendationResultSummary = {
  id: number;
  title: string;
  creditScore: number;
  userType: 'VULNERABLE' | 'STABLE';
  typeLabel: string;
  policyCount: number;
  savedAt: string;
};

export type SavedRecommendationResultDetail = {
  id: number;
  title: string;
  savedAt: string;
  result: DiagnoseResult;
};

// 온보딩 값을 요청 시점에 덮어쓸 때만 사용 (없으면 서버가 느슨하게 필터)
export type UserInputsOverride = {
  age?: number;
  regionCode?: string;
  annualIncome?: number;
  jobCode?: string;
  schoolCode?: string;
  marriageCode?: string;
  specializationCode?: string;
};

/**
 * POST /api/diagnose — 백엔드가 연동 저장된 KCB(kcb_connection)를 /v1/economic-feedback로
 * 보내 점수를 산정하고 정책을 추천한다. KCB 원본은 요청에 담지 않는다(연동이 선행되어야 함).
 */
export async function requestDiagnose(
  userInputsOverride?: UserInputsOverride,
): Promise<DiagnoseResult> {
  return api<DiagnoseResult>('/api/diagnose', {
    method: 'POST',
    auth: true,
    body: { userInputsOverride },
  });
}

/** 추천 요청이 진행 중일 때 표시할 서버 기준 생성 단계. */
export function getRecommendationProgress(): Promise<RecommendationProgress> {
  return api<RecommendationProgress>('/api/diagnose/progress', { auth: true });
}

/** 최신 진단의 점수·AI 리포트·추천 정책 전체를 한 번의 결과로 저장한다. */
export function saveRecommendationResult(): Promise<SavedRecommendationResultDetail> {
  return api<SavedRecommendationResultDetail>('/api/recommendations/saved', { method: 'POST', auth: true });
}

export function getSavedRecommendationResults(): Promise<SavedRecommendationResultSummary[]> {
  return api<SavedRecommendationResultSummary[]>('/api/recommendations/saved', { auth: true });
}

export function getSavedRecommendationResult(id: number): Promise<SavedRecommendationResultDetail> {
  return api<SavedRecommendationResultDetail>(`/api/recommendations/saved/${id}`, { auth: true });
}
