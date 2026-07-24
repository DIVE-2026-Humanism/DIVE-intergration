FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements.lock ./
RUN pip install -r requirements.lock

COPY config ./config
COPY src ./src
COPY Dataset/busan_policies.json Dataset/codebook.json ./Dataset/
COPY Dataset/개인_가계대출_*.csv Dataset/개인소득_및_카드소비_*.csv ./Dataset/
COPY Dataset/연도별_월평균_가구_소득_*.csv Dataset/월평균_가구_소득_*.xlsx ./Dataset/
RUN mkdir -p artifacts reports

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
