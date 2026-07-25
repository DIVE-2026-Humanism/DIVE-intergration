import { api } from './http';

export type NotificationItem = {
  id: number;
  title: string;
  body: string;
  type: string;
  read: boolean;
  createdAt: string; // ISO LocalDateTime
};

/** 최신순 알림 목록 */
export function getNotifications(): Promise<NotificationItem[]> {
  return api<NotificationItem[]>('/api/v1/members/me/notifications', { auth: true });
}

/** 안 읽은 개수 (배지용) */
export async function getUnreadCount(): Promise<number> {
  const res = await api<{ count: number }>('/api/v1/members/me/notifications/unread-count', { auth: true });
  return res.count;
}

/** 전체 읽음 처리 */
export function markAllNotificationsRead(): Promise<void> {
  return api<void>('/api/v1/members/me/notifications/read-all', { method: 'PATCH', auth: true });
}

/** 단건 읽음 처리 */
export function markNotificationRead(id: number): Promise<void> {
  return api<void>(`/api/v1/members/me/notifications/${id}/read`, { method: 'PATCH', auth: true });
}

// --- 알림 수신 설정 ---
export type NotificationSettings = { gonggu: boolean; policy: boolean; marketing: boolean };

/** 알림 수신 설정 조회 */
export function getNotificationSettings(): Promise<NotificationSettings> {
  return api<NotificationSettings>('/api/v1/members/me/notification-settings', { auth: true });
}

/** 알림 수신 설정 부분 변경 (바꾼 토글만 전송) → 변경 후 전체 설정 반환 */
export function updateNotificationSettings(patch: Partial<NotificationSettings>): Promise<NotificationSettings> {
  return api<NotificationSettings>('/api/v1/members/me/notification-settings', { method: 'PATCH', auth: true, body: patch });
}
