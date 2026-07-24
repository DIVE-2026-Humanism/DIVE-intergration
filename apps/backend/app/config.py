import os


class Settings:
    app_name: str = "DIVE 2026 API"
    api_prefix: str = "/api"

    # 모델팀 소유 외부 ai-server. 진단·유형분류·정책매칭·LLM설명 전부 여기서 처리.
    ai_server_base_url: str = os.getenv("AI_SERVER_BASE_URL", "https://ai.beceleb.org")
    ai_server_timeout_seconds: float = float(os.getenv("AI_SERVER_TIMEOUT_SECONDS", "35"))

    # 해커톤 데모라 인증 없음. 프론트 로컬 + 배포 도메인만 허용
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")


settings = Settings()
