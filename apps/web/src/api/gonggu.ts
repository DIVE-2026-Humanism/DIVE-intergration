import { env } from '../config/env';
import { ApiError, api } from './http';
import { tokenStore } from '../auth/tokenStore';
import { Gonggu } from '../types';

type GongguResponse = {
  id: number;
  writerNickname?: string;
  title: string;
  price: number;
  targetCount: number;
  currentCount: number;
  status: 'RECRUITING' | 'CLOSED' | 'COMPLETED' | 'FAILED';
  startDate: string;
  endDate: string;
  imageUrl: string | null;
  productUrl: string | null;
};

type GongguDetailResponse = GongguResponse & {
  writerNickname: string;
  content: string;
  createdAt: string;
};

type KakaoPayReadyResult = {
  paymentId: number;
  nextRedirectPcUrl: string;
  nextRedirectMobileUrl: string;
};

export type CreateGongguRequest = {
  title: string;
  content: string;
  price: number;
  targetCount: number;
  startDate: string;
  endDate: string;
  productUrl?: string;
  /** 상품을 식별하기 위한 대표 상품 이미지. 서버 multipart 필드명은 하위 호환을 위해 image를 유지한다. */
  productImage?: { uri: string; mimeType?: string | null };
};

const statusLabel: Record<GongguResponse['status'], string> = {
  RECRUITING: '모집 중',
  CLOSED: '모집 마감',
  COMPLETED: '공구 완료',
  FAILED: '공구 종료',
};

function getDeadline(endDate: string, status: GongguResponse['status']): string {
  if (status !== 'RECRUITING') return statusLabel[status];

  const remaining = new Date(endDate).getTime() - Date.now();
  if (!Number.isFinite(remaining) || remaining <= 0) return '마감임박';

  const days = Math.ceil(remaining / (1000 * 60 * 60 * 24));
  return days === 1 ? '오늘 마감' : `${days}일 남음`;
}

function getImageUrl(imageUrl: string | null): string | undefined {
  if (!imageUrl) return undefined;
  if (/^https?:\/\//i.test(imageUrl)) return imageUrl;
  return `${env.apiBaseUrl.replace(/\/$/, '')}/${imageUrl.replace(/^\//, '')}`;
}

function toGonggu(item: GongguResponse): Gonggu {
  const percent = item.targetCount > 0
    ? Math.round((item.currentCount / item.targetCount) * 100)
    : 0;

  return {
    id: String(item.id),
    brand: statusLabel[item.status],
    name: item.title,
    deadline: getDeadline(item.endDate, item.status),
    amount: `${item.price.toLocaleString('ko-KR')}원`,
    percent,
    imageUrl: getImageUrl(item.imageUrl),
    productUrl: item.productUrl ?? undefined,
    writerNickname: item.writerNickname,
    currentCount: item.currentCount,
    targetCount: item.targetCount,
    status: item.status,
    startDate: item.startDate,
    endDate: item.endDate,
  };
}

function toGongguDetail(item: GongguDetailResponse): Gonggu {
  return {
    ...toGonggu(item),
    writerNickname: item.writerNickname,
    content: item.content,
    productUrl: item.productUrl ?? undefined,
    createdAt: item.createdAt,
  };
}

/** 전체 공구 목록. GET /api/v1/gonggu/all */
export async function getGongguList(): Promise<Gonggu[]> {
  const list = await api<GongguResponse[]>('/api/v1/gonggu/all');
  return list.map(toGonggu);
}

/** 새 공동구매 등록. 현재는 이미지 없이도 등록할 수 있으며, 등록 후 목록을 다시 조회한다. */
export async function createGonggu(request: CreateGongguRequest): Promise<string> {
  const tokens = await tokenStore.load();
  if (!tokens) throw new ApiError('로그인이 필요합니다.', 401);

  const form = new FormData();
  form.append('title', request.title);
  form.append('content', request.content);
  form.append('price', String(request.price));
  form.append('targetCount', String(request.targetCount));
  form.append('startDate', request.startDate);
  form.append('endDate', request.endDate);
  if (request.productUrl?.trim()) form.append('productUrl', request.productUrl.trim());
  if (request.productImage?.uri) {
    const mimeType = request.productImage.mimeType?.toLowerCase().startsWith('image/')
      ? request.productImage.mimeType.toLowerCase()
      : 'image/jpeg';
    // MIME subtype에 확장자로 사용할 수 없는 값이 섞이지 않도록 제한합니다.
    const extension = mimeType.slice('image/'.length).replace(/[^a-z0-9]/g, '') || 'jpeg';
    // Expo 57의 Winter fetch는 RN의 {uri: ...} proprietary 파트를 지원하지 않습니다.
    // 로컬 URI를 Blob으로 읽어 append하면 Android/웹 양쪽에서 동일하게 처리됩니다.
    const imageResponse = await fetch(request.productImage.uri);
    if (!imageResponse.ok) {
      throw new ApiError('상품 이미지를 읽을 수 없습니다.', imageResponse.status);
    }
    const imageBlob = await imageResponse.blob();
    form.append('image', imageBlob, `product-image.${extension}`);
  }

  const response = await fetch(`${env.apiBaseUrl}/api/v1/gonggu`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tokens.accessToken}` },
    body: form,
  });
  const envelope = await response.json().catch(() => null) as { message?: string; code?: string; data?: number } | null;
  if (!response.ok || !envelope?.data) {
    throw new ApiError(envelope?.message ?? `공구 등록 실패 (${response.status})`, response.status, envelope?.code);
  }
  return String(envelope.data);
}

/** 공구 상세. GET /api/v1/gonggu/{id} */
export async function getGongguDetail(id: string): Promise<Gonggu> {
  const detail = await api<GongguDetailResponse>(`/api/v1/gonggu/${id}`);
  return toGongguDetail(detail);
}

/** 공구 좋아요 토글 — 이미 눌렀으면 취소. POST /api/v1/gonggu/{id} (로그인 필요) */
export async function toggleGongguLike(id: string): Promise<void> {
  return api<void>(`/api/v1/gonggu/${id}`, { method: 'POST', auth: true });
}

/** 내가 좋아요한 공구 목록. GET /api/v1/gonggu/myLike (로그인 필요) */
export async function getMyLikedGonggus(): Promise<Gonggu[]> {
  const list = await api<GongguResponse[]>('/api/v1/gonggu/myLike', { auth: true });
  return list.map(toGonggu);
}

/** 카카오페이 결제 준비. 반환된 모바일/PC 결제 URL을 바로 연다. */
export async function prepareGongguPayment(id: string): Promise<KakaoPayReadyResult> {
  return api<KakaoPayReadyResult>(`/api/v1/gonggu/payment/${id}/ready`, { method: 'POST', auth: true });
}
