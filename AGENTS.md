# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dify is an open-source platform for developing LLM applications with an intuitive interface combining agentic AI workflows, RAG pipelines, agent capabilities, and model management.

The codebase is split into:

- **Backend API** (`/api`): Python Flask application organized with Domain-Driven Design
- **Frontend Web** (`/web`): Next.js 15 application using TypeScript and React 19
- **A2A Gateway** (`/a2a-gateway`): FastAPI-based A2A Protocol gateway for agent-to-agent communication
- **Docker deployment** (`/docker`): Containerized deployment configurations

## Quick Start

### Docker Compose (Recommended)

```bash
cd docker
cp .env.example .env
docker compose up -d
```

Access at [http://localhost/install](http://localhost/install)

### Development Environment Setup

```bash
# Complete backend setup (middleware + web + api)
make dev-setup

# Or individual steps:
make prepare-docker  # Start middleware (PostgreSQL, Redis, etc.)
make prepare-web     # Install web dependencies
make prepare-api     # Install API dependencies and run migrations
```

**Important**: Backend requires Python 3.11-3.12 (not 3.13+) and uses `uv` for package management.

## Backend Development

### Running Commands

All backend commands must use `uv run --project api`:

```bash
# Run Flask commands
uv run --project api flask db upgrade

# Run pytest
uv run --project api --dev dev/pytest/pytest_unit_tests.sh
```

### Code Quality Checks

Before submitting backend changes, all checks must pass:

```bash
make lint         # Format and fix with ruff + import linter
make type-check   # Type check with basedpyright
```

Individual commands:
```bash
make format       # ruff format only
make check        # ruff check only (no fixes)
```

### Testing

```bash
# Run unit tests
uv run --project api --dev pytest api/tests/unit_tests/ -v

# Run specific test file
uv run --project api --dev pytest api/tests/unit_tests/services/test_account_service.py -v

# Run specific test function
uv run --project api --dev pytest api/tests/unit_tests/services/test_account_service.py::test_function_name -v
```

**Note**: Integration tests are CI-only and are not expected to run locally.

## Frontend Development

### Setup and Running

```bash
cd web
pnpm install
pnpm dev          # Start dev server with Turbopack
```

### Code Quality

```bash
pnpm lint         # Check for issues
pnpm lint:fix     # Fix auto-fixable issues
pnpm type-check   # TypeScript type checking
pnpm test         # Run Jest tests
```

### Internationalization

```bash
pnpm check-i18n      # Check i18n consistency
pnpm auto-gen-i18n   # Auto-generate translations
```

**Important**: User-facing strings must use `web/i18n/en-US/`. Never hardcode text in components.

## A2A Gateway Development

The A2A Gateway (`/a2a-gateway`) is a standalone FastAPI service that translates between A2A Protocol (JSON-RPC 2.0) and Dify API (REST + SSE).

### Running

```bash
# Via Docker Compose
cd docker
docker compose up a2a-gateway

# Local development
cd a2a-gateway
uv pip install -e .
uvicorn main:app --reload --port 8080
```

### Testing

```bash
cd a2a-gateway

# Unit tests (fast, no Docker needed)
pytest tests/unit/ -v

# Integration tests (requires running Dify instance)
pytest tests/integration/ -v

# All tests
./tests/run_tests.sh
```

**Test suite**: 31 tests (23 unit + 8 integration) ensure protocol conversion accuracy.

## Architecture Patterns

### Backend: Domain-Driven Design

The backend follows DDD and Clean Architecture principles:

```
api/
├── controllers/       # HTTP layer (Flask routes)
│   ├── console/      # Admin console APIs
│   ├── service_api/  # Service APIs (/v1/*)
│   └── web/          # Web app APIs (/api/*)
├── services/         # Business logic layer
├── repositories/     # Data access layer
├── models/           # Database models (SQLAlchemy)
├── core/             # Domain logic
│   ├── app/         # App execution engine
│   ├── agent/       # Agent runtime
│   ├── workflow/    # Workflow engine
│   └── rag/         # RAG pipeline
└── tasks/           # Celery async tasks
```

**Key principles**:
- Services contain business logic and orchestrate repositories
- Repositories handle data persistence
- Controllers are thin HTTP adapters
- Dependency injection through constructors
- Domain-specific exceptions at correct layers

### Frontend: Next.js App Router

```
web/
├── app/                  # App Router pages
├── service/             # API clients and services
├── context/             # React Context providers
├── hooks/               # Custom React hooks
└── i18n/                # Internationalization
```

**Key conventions**:
- Server components by default, client components when needed
- API calls through `service/` layer
- State management via Context API or Zustand
- All strings through i18n system

### A2A Gateway: Protocol Translation

```
a2a-gateway/
├── main.py              # FastAPI app entry point
├── config.py            # Environment configuration
├── models/              # Pydantic v2 data models
│   ├── a2a.py          # A2A Protocol schemas
│   └── dify.py         # Dify API schemas
├── services/            # Business logic
│   ├── dify_client.py  # Dify API HTTP client (httpx + SSE)
│   └── translator.py   # Protocol conversion logic
├── routers/             # FastAPI routes
└── tests/               # Test suite (pytest)
```

**Architecture**: Universal Router pattern - single gateway instance routes all A2A requests to Dify API.

## Async Work

- Backend async tasks use **Celery** with Redis as broker
- Tasks defined in `api/tasks/`
- Long-running operations (RAG indexing, workflow execution) run asynchronously

## Common Development Patterns

### Adding a New Backend Endpoint

1. Define route in `api/controllers/{console|service_api|web}/`
2. Implement business logic in `api/services/`
3. Add repository methods if database access needed
4. Write unit tests in `api/tests/unit_tests/`
5. Run `make lint` and `make type-check`

### Adding a New Frontend Page

1. Create page in `web/app/` (App Router)
2. Add i18n strings to `web/i18n/en-US/`
3. Create API service in `web/service/`
4. Add tests if complex logic
5. Run `pnpm lint` and `pnpm type-check`

## Type Safety

### Python

- Use explicit type hints on all functions and class attributes
- Avoid `Any` - prefer specific types or type unions
- Type hints help with IDE autocomplete and catch bugs early
- Run `make type-check` (basedpyright) before committing

### TypeScript

- Strict mode enabled
- Avoid `any` - use `unknown` or specific types
- Interface over type for object shapes
- Run `pnpm type-check` before committing

## Testing Philosophy

- Follow TDD: red → green → refactor
- **Arrange-Act-Assert** pattern for all tests
- Unit tests should be fast and not require external services
- Integration tests verify full system behavior
- Write self-documenting tests with clear names

## Environment Requirements

- **Python**: 3.11 or 3.12 (not 3.13+)
- **Node.js**: >=22.11.0
- **pnpm**: 10.19.0+ (enforced by preinstall hook)
- **Docker**: For local development middleware

## Clean Development

```bash
# Clean all dev environment (stops containers, removes volumes)
make dev-clean
```

**Warning**: This removes all local data including database and storage.
