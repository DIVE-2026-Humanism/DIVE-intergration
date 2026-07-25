# systemd·Docker 없는 환경에서 직접 실행

이 환경은 `CAP_NET_ADMIN`과 `CAP_SYS_ADMIN`이 없어 Docker daemon의 bridge/NAT 및
mount propagation을 만들 수 없다. Compose를 반복 실행하지 않고 PostgreSQL, Ollama,
FastAPI를 일반 프로세스로 실행한다. 기존 Compose와 Dockerfile은 변경하지 않는다.
호스트 NVIDIA 드라이버가 535이므로 Ollama는 이 드라이버와 호환되는 0.11.10으로
고정한다. 최신 Ollama는 드라이버 550 이상을 요구해 이 환경에서 CPU로 전환된다.

## 최초 준비와 실행

Ubuntu 패키지와 드라이버 535 호환 Ollama를 한 번 설치한다.

```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-client curl ca-certificates zstd
curl -fsSL https://ollama.com/install.sh -o /tmp/ollama-install.sh
OLLAMA_VERSION=0.11.10 sudo -E sh /tmp/ollama-install.sh
```

```bash
cd "$HOME/DIVE-intergration/LLM service"
./scripts/native_setup.sh
./scripts/native_start.sh
```

최초 시작은 `qwen3:8b`를 다운로드하고 `dive-qwen3:8b`를 만들기 때문에 수 GB의
네트워크 전송이 발생한다. 데이터와 로그는 `.native/` 아래에 보존된다.

## 상태와 중지

```bash
./scripts/native_status.sh
curl http://127.0.0.1:8000/health/ready
./scripts/native_stop.sh
```

로그는 `.native/logs/postgres.log`, `.native/logs/ollama.log`,
`.native/logs/api.log`에서 확인한다. systemd가 없으므로 Elice 컨테이너 자체가
재시작되면 `native_start.sh`를 다시 실행해야 한다.
