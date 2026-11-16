.PHONY: help up down logs env install migrate seed api worker beat web test test-backend test-frontend lint typecheck build check

help:
	@echo "make up            - docker compose up --build (full stack, mock providers)"
	@echo "make install       - install backend + frontend deps locally"
	@echo "make migrate seed  - run migrations / load demo data"
	@echo "make api worker beat web - run services locally"
	@echo "make check         - lint + typecheck + tests + build"

env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

up: env
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend worker

install:
	cd backend && pip install -r requirements-dev.txt
	cd frontend && npm install

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m app.cli seed

api:
	cd backend && uvicorn app.main:app --reload --port 8000

worker:
	cd backend && celery -A app.workers.celery_app worker -Q default,whatsapp,webhooks,documents --loglevel=INFO

beat:
	cd backend && celery -A app.workers.celery_app beat --loglevel=INFO

web:
	cd frontend && npm run dev

test-backend:
	cd backend && pytest

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

lint:
	cd backend && ruff check app tests
	cd frontend && npm run lint

typecheck:
	cd backend && mypy app
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

check: lint typecheck test build
