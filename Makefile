.PHONY: dev test seed lint deploy smoke

dev:
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

test:
	cd backend && uv run pytest

seed:
	cd backend && uv run python -m app.db.seed

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run typecheck

deploy:
	cd frontend && npm run build
	modal deploy deploy/modal_app.py

smoke:
	@test -n "$(URL)" || (echo "usage: make smoke URL=https://..." && exit 1)
	curl -fsS "$(URL)/api/health" && echo
	curl -fsS -o /dev/null -w "app shell: %{http_code}\n" "$(URL)/"
