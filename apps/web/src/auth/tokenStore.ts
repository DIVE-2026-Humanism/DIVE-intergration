import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

// 토큰 저장소. 네이티브는 expo-secure-store, 웹은 localStorage 사용.
const ACCESS = 'jg_access_token';
const REFRESH = 'jg_refresh_token';

const isWeb = Platform.OS === 'web';

async function setItem(key: string, value: string) {
  if (isWeb) { try { window.localStorage.setItem(key, value); } catch {} return; }
  await SecureStore.setItemAsync(key, value);
}
async function getItem(key: string): Promise<string | null> {
  if (isWeb) { try { return window.localStorage.getItem(key); } catch { return null; } }
  return SecureStore.getItemAsync(key);
}
async function removeItem(key: string) {
  if (isWeb) { try { window.localStorage.removeItem(key); } catch {} return; }
  await SecureStore.deleteItemAsync(key);
}

export type Tokens = { accessToken: string; refreshToken: string };

export const tokenStore = {
  async save({ accessToken, refreshToken }: Tokens) {
    await Promise.all([setItem(ACCESS, accessToken), setItem(REFRESH, refreshToken)]);
  },
  async load(): Promise<Tokens | null> {
    const [accessToken, refreshToken] = await Promise.all([getItem(ACCESS), getItem(REFRESH)]);
    if (!accessToken || !refreshToken) return null;
    return { accessToken, refreshToken };
  },
  async clear() {
    await Promise.all([removeItem(ACCESS), removeItem(REFRESH)]);
  },
};
