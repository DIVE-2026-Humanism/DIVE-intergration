import { api } from './http';

/** 최근 검색어 목록 (최신순, 최대 10) */
export function getSearchHistory(): Promise<string[]> {
  return api<string[]>('/api/v1/members/me/search-history', { auth: true });
}

/** 검색어 기록 */
export function addSearchHistory(keyword: string): Promise<void> {
  return api<void>('/api/v1/members/me/search-history', { method: 'POST', auth: true, body: { keyword } });
}

/** 검색어 단건 삭제 */
export function removeSearchHistory(keyword: string): Promise<void> {
  return api<void>(`/api/v1/members/me/search-history?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE', auth: true });
}

/** 검색 이력 전체 삭제 */
export function clearSearchHistory(): Promise<void> {
  return api<void>('/api/v1/members/me/search-history', { method: 'DELETE', auth: true });
}
