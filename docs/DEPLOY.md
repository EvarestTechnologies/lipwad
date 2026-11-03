# Lipwad — CI/CD and Deployment

## Why Modal
- It is a hackathon inference partner, offering $100 in credits for running Meta's open-weight models. The Muse Glimmer endpoint runs there too, so one account covers hosting and triage.
- Deploying is one terminal command (`modal deploy`), with no Terraform, container registry or IAM setup. That matters for a solo build with an eight-day window.
- FastAPI runs as an ASGI app, and the built React PWA is served by the same app, so there is one URL for judges.

## Topology
```
GitHub (public repo)
  └─ Actions: ci.yml ── on every push and PR: lint, typecheck, pytest (mock HIE, stub models), frontend build
              deploy.yml ── on push to main, after CI passes: modal deploy
Modal app "lipwad"
  ├─ web function (FastAPI ASGI) ── /api/* plus the static PWA from frontend/dist
  ├─ Volume "lipwad-data" ── SQLite database and uploads (DATABASE_URL, UPLOAD_DIR point here)
  └─ Secret "lipwad-env" ── provider keys, created from .env, never committed
Model providers ── Meta Model API, Baseten (Muse Spark Open), Modal (Muse Glimmer)
```
SQLite on a Volume allows one writer, so the web function is capped at one container (`max_containers=1`). That is enough for a demo; Postgres comes later through `DATABASE_URL`.

## Terminal deployment
One-time setup:
```bash
uv tool install modal
modal setup                                          # browser login, stores the token locally
modal secret create lipwad-env --from-dotenv .env    # rerun with --force after changing keys
```
Every deploy:
```bash
make deploy      # npm run build in frontend/, then modal deploy deploy/modal_app.py
```
The live app is at https://stellaacharoiro--lipwad-web.us-east.modal.run. Smoke-test it with `make smoke URL=<live url>`, which checks `/api/health` and the app shell. On first start the container seeds the synthetic cases onto the Volume.

## CI (`.github/workflows/ci.yml`)
Runs on every push and pull request:
1. `uv sync`, then `ruff check`, `ruff format --check` and `pytest` with `HIE_MODE=mock` and stub model providers. CI never calls a paid model.
2. `npm ci`, then `tsc --noEmit` and `vite build` for the frontend.
3. A secret scan that fails if anything resembling a key appears in the diff.
4. Muse Code review: `muse exec` runs headlessly with a review-only prompt against the PR diff (no file writes, no `--yolo`) and posts its findings as a job summary. It authenticates with `META_API_KEY` and is skipped when that repo secret is not set.

## CD (`.github/workflows/deploy.yml`, not yet added)
Deploys currently run from the terminal with `make deploy`. The workflow below needs a Modal token stored as GitHub secrets before it can be added. Once added, it runs on push to `main` once CI passes, and can also be started by hand with `workflow_dispatch`:
1. Build the frontend.
2. `modal deploy deploy/modal_app.py`, using the GitHub secrets `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`.
3. Run the smoke test against the live URL and fail the job if it doesn't pass.

The provider keys stay in the Modal secret. GitHub only holds the Modal token and the Meta key used for the Muse Code review job.

## Environments
| Environment | How | Models | HIE |
|---|---|---|---|
| Local | `make dev` | Real or stub, set in `.env` | mock |
| CI | GitHub Actions | stub | mock |
| Live (judges) | Modal, from `main` | real Meta models | mock (sandbox if access is granted) |

## Dates
| Date | Milestone |
|---|---|
| Nov 2 | CI green; walking skeleton live on Modal |
| Daily | Every merge to `main` auto-deploys; smoke test passes |
| Nov 3 | Last full day of hackathon troubleshooting support |
| Nov 4, midday ET | Feature freeze |
| Nov 4, 9 PM ET | Submission: public repo, live URL, 3-minute video |
| Nov 5 – Nov 16 | Keep warm (`min_containers=1`) through judging, finals (Nov 9) and the community vote |

## Cost guardrails
- Spend limits on Meta, Baseten and Modal billing pages.
- The web function scales to zero during the build window and is kept warm only from Nov 5.
- Tests and CI use stub providers. Real-model checks are run by hand with `make eval`.
