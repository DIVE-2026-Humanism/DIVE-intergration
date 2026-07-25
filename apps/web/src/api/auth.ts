import { api } from './http';
import { tokenStore, Tokens } from '../auth/tokenStore';

// GET /api/v1/members/me 의 data 형태
export type Member = { id: number; email: string | null; nickname: string | null; role: string; career: string; finalEducation: string };

/**
 * 카카오 인가코드를 백엔드로 넘겨 자체 JWT를 발급받고 저장한다.
 * POST /api/auth/kakao  { code, redirectUri } -> { accessToken, refreshToken } (래퍼 없음)
 */
export async function kakaoLogin(code: string, redirectUri: string): Promise<Tokens> {
  const tokens = await api<Tokens>('/api/auth/kakao', { method: 'POST', body: { code, redirectUri }, raw: true });
  await tokenStore.save(tokens);
  return tokens;
}

/** GET /api/v1/members/me */
export function getMe(): Promise<Member> {
  return api<Member>('/api/v1/members/me', { auth: true });
}

/**
 * PATCH /api/v1/members/me/onboarding { career, finalEducation }
 * 프론트의 직군(jobCd)/학력(schoolCd) 라벨을 career/finalEducation으로 전달.
 */
export function submitOnboarding(career: string, finalEducation: string): Promise<Member> {
  return api<Member>('/api/v1/members/me/onboarding', { method: 'PATCH', auth: true, body: { career, finalEducation } });
}

/** PATCH /api/v1/members/me/profile — 닉네임/직군/학력 수정 */
export function updateMyProfile(nickname: string, career: string, finalEducation: string): Promise<Member> {
  return api<Member>('/api/v1/members/me/profile', { method: 'PATCH', auth: true, body: { nickname, career, finalEducation } });
}

/** POST /api/auth/logout (Bearer AT + { refreshToken }) 후 로컬 토큰 삭제 */
export async function logout(): Promise<void> {
  const tokens = await tokenStore.load();
  try {
    if (tokens) await api<void>('/api/auth/logout', { method: 'POST', auth: true, body: { refreshToken: tokens.refreshToken } });
  } catch {
    // 서버 로그아웃 실패해도 로컬 세션은 정리한다
  }
  await tokenStore.clear();
}

/** 앱 시작 시 저장된 토큰으로 세션 복구 시도 */
export async function restoreSession(): Promise<Member | null> {
  const tokens = await tokenStore.load();
  if (!tokens) return null;
  try { return await getMe(); } catch { return null; }
}
