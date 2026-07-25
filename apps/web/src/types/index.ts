// category는 서버 대분류명(lclsfNm)이 그대로 들어올 수 있어 string으로 둔다.
export type Policy = {
  id: string;
  title: string;
  category: string;
  subCategory: string;
  summary: string;
  benefit: string;
  period: string;
  deadline: string;
  days: number;
  popularity: number;
  description: string;
  institution: string;
  targetAge: string;
  applyUrl: string;
};

export type PolicyDetail = Policy & {
  keywords: string;
  applicationMethod: string;
  screeningMethod: string;
  documents: string;
  supportScale: string;
  incomeCondition: string;
  additionalCondition: string;
  participationRestriction: string;
};
export type Gonggu = {
  id: string;
  brand: string;
  name: string;
  deadline: string;
  amount: string;
  percent: number;
  imageUrl?: string;
  productUrl?: string;
  writerNickname?: string;
  content?: string;
  currentCount?: number;
  targetCount?: number;
  status?: 'RECRUITING' | 'CLOSED' | 'COMPLETED' | 'FAILED';
  startDate?: string;
  endDate?: string;
  createdAt?: string;
};
