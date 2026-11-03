.PHONY: dev test seed lint deploy smoke review-all

dev:
	(cd backend && set -a && { [ -f ../.env ] && . ../.env; true; } && set +a && LIPWAD_SERVE_API=1 uv run uvicorn app.main:app --reload --port 8000) & \
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

review-all:
	@test -n "$(URL)" || (echo "usage: make review-all URL=https://..." && exit 1)
	for case in C01 C02 C03 F01 F02 F03 F04 F05 F07 F08 F09; do \
		curl -fsS -X POST "$(URL)/api/claims/$$case/run" -o /dev/null -w "$$case %{http_code} %{time_total}s\n"; \
	done
