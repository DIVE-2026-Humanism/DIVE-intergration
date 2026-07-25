const apiBaseUrl = (process.env.EXPO_PUBLIC_API_BASE_URL ?? 'https://api.example.com').replace(/\/$/, '');

export const env = {
  apiBaseUrl,
  appEnv: process.env.EXPO_PUBLIC_APP_ENV ?? 'development',
  // 카카오 REST API 키 (백엔드 KAKAO_CLIENT_ID와 동일해야 함 — authorize의 client_id로 사용)
  kakaoRestApiKey: process.env.EXPO_PUBLIC_KAKAO_REST_API_KEY ?? '',
  // API 주소에서 파생해 인가 요청과 토큰 교환에 항상 같은 콜백 URL을 사용한다.
  kakaoRedirectUri: `${apiBaseUrl}/api/auth/kakao/callback`,
} as const;
