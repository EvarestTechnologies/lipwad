.PHONY: dev test seed lint

dev:
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

test:
	cd backend && uv run pytest

seed:
	@echo "Seed loader arrives with the synthetic data issue." && exit 1

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run typecheck
