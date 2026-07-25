# 잡공구

부산시 정책과 공동구매를 연결하는 Expo React Native 프로토타입입니다. 제공된 와이어프레임을 기준으로 홈, 정책, 맞춤 추천, 공동구매, 마이 페이지 플로우를 구현했습니다.

## 실행

```bash
npm install
Copy-Item .env.example .env
npx expo start
```

`.env`의 `EXPO_PUBLIC_API_BASE_URL`, `EXPO_PUBLIC_KAKAO_LOGIN_KEY`를 실제 값으로 교체하세요. 현재 `src/api/`는 화면 동작을 위한 mock 데이터를 반환하며, 실제 API 연동 시 같은 함수 계약을 유지하도록 구성했습니다.
