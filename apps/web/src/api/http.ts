import { env } from '../config/env';
import { tokenStore } from '../auth/tokenStore';

// 백엔드 공통 응답 래퍼 (ApiResponse<T>)
type ApiEnvelope<T> = { success: boolean; message: string; data: T; code: string };

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Options = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  auth?: boolean;      // Authorization: Bearer 헤더 부착 여부
  raw?: boolean;       // true면 ApiResponse 언랩 없이 원본 JSON 반환 (예: /api/auth/kakao)
  _retried?: boolean;  // 401 재발급 후 1회 재시도 플래그
};

async function refreshTokens(): Promise<boolean> {
  const tokens = await tokenStore.load();
  if (!tokens) return false;
  try {
    const res = await fetch(`${env.apiBaseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken: tokens.refreshToken }),
    });
    if (!res.ok) return false;
    const json = (await res.json()) as ApiEnvelope<{ accessToken: string; refreshToken: string }>;
    if (!json?.data?.accessToken) return false;
    await tokenStore.save({ accessToken: json.data.accessToken, refreshToken: json.data.refreshToken });
    return true;
  } catch {
    return false;
  }
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const { method = 'GET', body, auth = false, raw = false, _retried = false } = opts;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const tokens = await tokenStore.load();
    if (tokens) headers.Authorization = `Bearer ${tokens.accessToken}`;
  }

  const res = await fetch(`${env.apiBaseUrl}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // 만료된 access token → 1회 재발급 후 재시도
  if (res.status === 401 && auth && !_retried) {
    if (await refreshTokens()) return api<T>(path, { ...opts, _retried: true });
  }

  if (res.status === 204) return undefined as T;

  let json: unknown = null;
  try { json = await res.json(); } catch { /* 빈 바디 허용 */ }

  if (!res.ok) {
    const env2 = json as Partial<ApiEnvelope<unknown>> | null;
    throw new ApiError(env2?.message ?? `요청 실패 (${res.status})`, res.status, env2?.code);
  }

  if (raw) return json as T;
  return (json as ApiEnvelope<T>).data;
}
