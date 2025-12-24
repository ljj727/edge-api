# Edge Backend API

FastAPI 기반의 Edge Backend API 서버입니다. 기존 C# ASP.NET Core 백엔드에서 포팅되었습니다.

## 개요

Edge Backend는 비디오 분석 시스템의 백엔드 API 서버로, 다음 기능을 제공합니다:

- **이벤트 관리**: 감지 이벤트 저장, 조회, 통계
- **비디오 스트림 관리**: 카메라/스트림 등록 및 설정
- **추론 설정**: AI 모델 추론 구성 관리
- **앱 관리**: AI 앱 설치 및 관리
- **웹훅**: 이벤트 푸시 알림
- **VMS 연동**: ViveEX (Mx) 연동

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      Edge Backend (FastAPI)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  Auth   │  │ Events  │  │ Videos  │  │Inference│  ...   │
│  │ Router  │  │ Router  │  │ Router  │  │ Router  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│  ┌────┴────────────┴────────────┴────────────┴────┐        │
│  │              Service Layer                      │        │
│  │  (AuthService, EventService, VideoService...)   │        │
│  └────┬────────────────────────────────────────────┘        │
│       │                                                     │
│  ┌────┴─────────────────────────────────────────────────┐  │
│  │                  SQLAlchemy ORM                       │  │
│  │              (Async SQLite Database)                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    NATS     │  │    gRPC     │  │  Scheduler  │         │
│  │ Subscriber  │  │   Client    │  │ (APScheduler)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
         │                  │
         ▼                  ▼
   ┌──────────┐      ┌──────────┐
   │   NATS   │      │   Core   │
   │  Server  │      │ (gRPC)   │
   └──────────┘      └──────────┘
```

## 기술 스택

| 구분 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI 0.109+ |
| ORM | SQLAlchemy 2.0 (async) |
| 데이터베이스 | SQLite (aiosqlite) |
| 인증 | JWT (python-jose) |
| 유효성검사 | Pydantic v2 |
| 메시징 | NATS (nats-py) |
| RPC | gRPC (grpcio) |
| 스케줄러 | APScheduler |
| HTTP 클라이언트 | httpx |

## 요구사항

- Python 3.11+
- NATS Server (선택)
- Core/Detector gRPC Server (선택)

## 설치

```bash
# 저장소 클론
git clone <repository-url>
cd edge/backend

# 가상환경 생성 (권장)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# 의존성 설치
pip install -e .

# 개발용 의존성 포함 설치
pip install -e ".[dev]"
```

## 설정

환경변수 또는 `.env` 파일로 설정합니다:

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# 필요에 따라 값 수정
```

### 주요 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DEBUG` | false | 디버그 모드 |
| `PORT` | 8400 | 서버 포트 |
| `DATA_SAVE_FOLDER` | /opt/autocare/dx/volume/DxApi | 데이터 저장 경로 |
| `DB_FILE` | DxApi.db | SQLite 파일명 |
| `JWT_SECRET_KEY` | (기본키) | JWT 서명 키 |
| `NATS_URI` | nats://localhost:4222 | NATS 서버 주소 |
| `CORE_GRPC_SERVER` | 127.0.0.1:50051 | Core gRPC 주소 |

## 실행

### 개발 서버

```bash
# 방법 1: 직접 실행
python -m app.main

# 방법 2: uvicorn으로 실행 (hot reload)
uvicorn app.main:app --reload --port 8400

# 방법 3: 디버그 모드
DEBUG=true uvicorn app.main:app --reload --port 8400
```

### 프로덕션

```bash
# Gunicorn + Uvicorn workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8400
```

### Docker

```bash
# 이미지 빌드
docker build -t edge-backend .

# 컨테이너 실행
docker run -d \
  -p 8400:8400 \
  -v /opt/autocare/dx:/opt/autocare/dx \
  -e NATS_URI=nats://host.docker.internal:4222 \
  edge-backend
```

## API 문서

서버 실행 후 Swagger UI에서 API 문서를 확인할 수 있습니다:

- Swagger UI: http://localhost:8400/swagger (DEBUG=true 필요)
- ReDoc: http://localhost:8400/redoc (DEBUG=true 필요)

### API 엔드포인트 요약

| 경로 | 설명 |
|------|------|
| `POST /api/v2/auth` | 로그인 (JWT 토큰 발급) |
| `GET /api/v2/events` | 이벤트 조회 |
| `GET /api/v2/events/summary` | 이벤트 요약 통계 |
| `GET /api/v2/events/trend` | 이벤트 트렌드 데이터 |
| `GET /api/v2/videos` | 비디오 목록 |
| `POST /api/v2/videos` | 비디오 등록 |
| `GET /api/v2/inference` | 추론 설정 조회 |
| `POST /api/v2/inference` | 추론 설정 등록 |
| `GET /api/v2/apps` | 앱 목록 |
| `POST /api/v2/eventpushes` | 웹훅 등록 |
| `GET /api/v2/mx` | ViveEX 계정 목록 |
| `GET /api/v2/system` | 시스템 정보 |

## 테스트

```bash
# 전체 테스트 실행
pytest

# 커버리지 포함
pytest --cov=app --cov-report=html

# 특정 테스트 실행
pytest tests/test_events.py -v
```

## 프로젝트 구조

```
backend/
├── app/
│   ├── api/
│   │   └── v2/              # API v2 라우터
│   │       ├── auth.py      # 인증
│   │       ├── events.py    # 이벤트
│   │       ├── videos.py    # 비디오
│   │       ├── inference.py # 추론
│   │       └── ...
│   ├── core/
│   │   ├── config.py        # 설정 관리
│   │   ├── deps.py          # 의존성 주입
│   │   └── security.py      # 보안 유틸리티
│   ├── db/
│   │   ├── base.py          # DB 베이스 모델
│   │   └── session.py       # DB 세션
│   ├── grpc/
│   │   └── detector_client.py  # Core gRPC 클라이언트
│   ├── models/              # SQLAlchemy 모델
│   ├── schemas/             # Pydantic 스키마
│   ├── services/            # 비즈니스 로직
│   ├── workers/             # 백그라운드 워커
│   │   ├── nats_subscriber.py
│   │   ├── eventpush_worker.py
│   │   └── ...
│   └── main.py              # 앱 진입점
├── migrations/              # Alembic 마이그레이션
├── tests/                   # 테스트
├── pyproject.toml           # 프로젝트 설정
├── Dockerfile
└── README.md
```

## 데이터베이스 마이그레이션

```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
alembic upgrade head

# 롤백
alembic downgrade -1
```

## 기여

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 라이선스

Proprietary - All rights reserved
