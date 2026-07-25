import { api } from './http';

// 백엔드 KcbConnectionController.Response 계약
export type KcbConnectResult = {
  id: number;
  createdAt: string; // LocalDateTime
  dummy: boolean;
  creditScore: number;
  creditGrade: string;
};

/** POST /api/v1/kcb/connect — 더미 KCB 정보를 DB에 저장(연동) */
export async function connectKcb(): Promise<KcbConnectResult> {
  return api<KcbConnectResult>('/api/v1/kcb/connect', { method: 'POST', auth: true });
}
