.PHONY: dev test seed lint deploy smoke review-all snapshot supersede

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

LIVE_URL ?= https://stellaacharoiro--lipwad-web.us-east.modal.run

deploy:
	cd frontend && npm run build
	modal deploy deploy/modal_app.py
	$(MAKE) smoke URL=$(LIVE_URL)

# Fails if the app, its shell or the reasoning model is down. The reasoning check makes at
# most one small model call per 10 minutes.
smoke:
	@test -n "$(URL)" || (echo "usage: make smoke URL=https://..." && exit 1)
	curl -fsS --retry 10 --retry-all-errors --retry-delay 3 "$(URL)/api/health" && echo
	curl -fsS -o /dev/null -w "app shell: %{http_code}\n" "$(URL)/"
	@curl -sS "$(URL)/api/health/reasoning" -w "\n" -o /tmp/lipwad-reasoning.json; cat /tmp/lipwad-reasoning.json; echo; \
		grep -q '"status":"ok"' /tmp/lipwad-reasoning.json || (echo "REASONING CHECK FAILED: explanations would show as not available" && exit 1)

review-all:
	@test -n "$(URL)" || (echo "usage: make review-all URL=https://..." && exit 1)
	for case in C01 C02 C03 C04 F01 F02 F03 F04 F05 F06 F07 F08 F09 F10; do \
		curl -fsS -X POST "$(URL)/api/claims/$$case/run" -o /dev/null -w "$$case %{http_code} %{time_total}s\n"; \
	done

snapshot:
	@test -n "$(URL)" || (echo "usage: make snapshot URL=https://..." && exit 1)
	@set -a && . ./.env && set +a && curl -fsS -X POST -H "x-admin-key: $$LIPWAD_ADMIN_KEY" "$(URL)/api/demo/snapshot" && echo " snapshot saved"

# Hide explanations written before BEFORE (an ISO time), keeping them in the audit trail.
supersede:
	@test -n "$(URL)" -a -n "$(BEFORE)" || (echo "usage: make supersede URL=https://... BEFORE=2026-11-18T12:41:00Z" && exit 1)
	@set -a && . ./.env && set +a && curl -fsS -X POST "$(URL)/api/demo/supersede-explanations" \
		-H "x-admin-key: $$LIPWAD_ADMIN_KEY" -H "content-type: application/json" -d '{"before":"$(BEFORE)"}' && echo

