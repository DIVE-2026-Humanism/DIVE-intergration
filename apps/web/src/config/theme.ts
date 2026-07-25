// ON:GIL 컬러 시스템 (딥 네이비 · 오션 블루 · 소프트 민트 · 희망 옐로 · 블루 화이트)
export const theme = {
  // 배경/표면
  background: '#FFFFFF', // 화이트 (앱 전체 배경)
  surface: '#EFF8FD',    // Blue 50 (섹션/연한 강조 배경)
  surfaceAlt: '#E4EDF2', // Navy 100 (태그·연한 보더)
  surfaceWhite: '#FFFFFF',

  // 텍스트
  text: '#172B3A',       // Text Primary
  textMuted: '#5F7482',  // Text Secondary
  textFaint: '#8C9CA6',  // Text Tertiary

  // 브랜드
  navy: '#173B57',       // Brand Navy (ON)
  accent: '#3B82C4',     // Ocean Blue (GIL, Primary 버튼/활성)
  accentDark: '#1E5681', // Blue 900 (pressed)
  blueBg: '#DCEFFA',     // Blue 100 (선택 칩/카드 강조 배경)

  // 민트 (선택·긍정)
  mint: '#73CDB3',
  mintText: '#357F6C',
  mintBg: '#DFF5EE',

  // 옐로 (알림·마감임박·작은 포인트)
  yellow: '#F4C96B',
  yellowText: '#896515',
  yellowBg: '#FFF1C9',

  // 코랄 (주의 — 낮은 채도)
  caution: '#A9574F',
  cautionBg: '#FDEAE7',

  // 라인/구분
  border: '#D8E3E9',
  divider: '#E8EFF3',

  // 헤더 그라디언트 상단, 공구 카드 이미지 그라디언트
  headerTop: '#EFF8FD',
  cardImgA: '#DCEFFA',
  cardImgB: '#9BC9E9',
} as const;
