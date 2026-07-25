import { useCallback } from 'react';
import * as WebBrowser from 'expo-web-browser';
import { env } from '../config/env';
import { kakaoLogin, getMe, Member } from '../api/auth';

// 인증 세션 정리 (권장)
WebBrowser.maybeCompleteAuthSession();

const KAKAO_AUTHORIZE = 'https://kauth.kakao.com/oauth/authorize';
// 백엔드 콜백(/api/auth/kakao/callback)이 302로 되돌려보내는 앱 딥링크
const APP_RETURN_URL = 'jabgonggu://auth';

function parseParam(url: string, key: string): string | null {
  const m = url.match(new RegExp('[?&#]' + key + '=([^&#]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

/**
 * 카카오 로그인 훅 (백엔드 콜백 bounce 방식).
 *
 * 흐름: 앱이 카카오 authorize를 auth 세션으로 연다 → redirect_uri는 백엔드 콜백(HTTP,
 * 카카오는 커스텀 스킴 등록 불가) → 백엔드가 302로 jabgonggu://auth?code=... 로 되돌려보냄
 * → openAuthSessionAsync가 그 딥링크에서 resolve(폴링 아님, 이벤트) → code를 꺼내
 * POST /api/auth/kakao 로 교환 → 토큰 저장 → getMe.
 *
 * redirect_uri는 authorize와 토큰 교환(kakaoLogin) 양쪽에 "정확히 동일한 값"을 써야 한다.
 */
export function useKakaoAuth(
  onAuthenticated: (member: Member) => void,
  onError?: (message: string) => void,
) {
  const signIn = useCallback(async () => {
    if (!env.kakaoRestApiKey) {
      onError?.('카카오 REST API 키가 설정되지 않았어요. .env를 확인해주세요.');
      return;
    }
    const redirectUri = env.kakaoRedirectUri; // 백엔드 콜백 URL
    if (!redirectUri) {
      onError?.('카카오 Redirect URI가 설정되지 않았어요. .env를 확인해주세요.');
      return;
    }

    const authUrl =
      `${KAKAO_AUTHORIZE}?response_type=code` +
      `&client_id=${encodeURIComponent(env.kakaoRestApiKey)}` +
      `&redirect_uri=${encodeURIComponent(redirectUri)}`;

    try {
      // 브라우저가 jabgonggu://auth 로 돌아오면 세션이 resolve됨
      const result = await WebBrowser.openAuthSessionAsync(authUrl, APP_RETURN_URL);
      if (result.type !== 'success' || !('url' in result) || !result.url) {
        onError?.('로그인이 취소되었어요.');
        return;
      }
      const error = parseParam(result.url, 'error');
      if (error) {
        onError?.(parseParam(result.url, 'error_description') ?? '카카오 인증에 실패했어요.');
        return;
      }
      const code = parseParam(result.url, 'code');
      if (!code) {
        onError?.('카카오 인가코드를 받지 못했어요.');
        return;
      }
      await kakaoLogin(code, redirectUri);
      onAuthenticated(await getMe());
    } catch (e) {
      onError?.(e instanceof Error ? e.message : '로그인에 실패했어요.');
    }
  }, [onAuthenticated, onError]);

  return { ready: true, signIn };
}
