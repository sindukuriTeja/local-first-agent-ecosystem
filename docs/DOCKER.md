# Docker & Multi-Portal Web App

Run the whole platform — 16-agent backend, local Ollama inference, and the
7-portal React web app — with a single command.

## Quick start

```bash
docker compose up --build
```

Then open **http://localhost:8000** and sign in with any demo account.

What happens on first start:

1. `ollama` container starts (local LLM runtime).
2. `ollama-init` pulls the two models the platform needs:
   - `llama3.1:8b` (chat / reasoning)
   - `nomic-embed-text` (local embeddings for vector search)

   The first pull is large (~5 GB) and can take a while. Afterwards the
   models persist in the `ollama_models` volume, so later starts are fast.
3. `app` builds the React frontend (Vite) and starts the FastAPI backend,
   which serves both the JSON API and the web app.

> The app is fully usable even before the models finish pulling — every
> portal, login, document, request, approval and audit feature works. Only
> the **AI-assisted tasks** need a model, and they degrade gracefully with a
> clear "Ollama not reachable" message until one is available.

## Demo logins (shown on the login screen)

| Portal | Username | Password |
|---|---|---|
| Internal Employee | `employee1` | `employee123` |
| Management / Executive | `manager1` | `manager123` |
| Advocate / External Counsel | `counsel1` | `counsel123` |
| Client | `client1` | `client123` |
| Tenant / Buyer / Vendor | `tenant1` | `tenant123` |
| Regulator / Auditor | `auditor1` | `auditor123` |
| Admin / System Administrator | `admin` | `admin123` |

Legacy accounts `reviewer` / `reviewer123` and `analyst` / `analyst123` also
work (they map to the admin and employee portals respectively).

These are **demo-grade** credentials, intentionally shown on the login
screen. For any real deployment you must change them and put the app behind
proper authentication — see the security note at the bottom.

## What each portal shows

- **Internal Employee** — assigned cases, tax matters, legal work, drafts,
  all in-scope documents, and AI-assisted tasks.
- **Management / Executive** — firm-wide KPIs, workload by matter, risk
  alerts, sensitivity distribution, pending approvals, recent activity.
- **Advocate / External Counsel** — assigned cases, drafts to review, legal
  research, AI-assisted tasks.
- **Client** — submit requests, upload documents, track cases, read reviewed
  reports, see request history.
- **Tenant / Buyer / Vendor** — parcels/projects, submit requests, upload
  documents, receive updates, request history.
- **Regulator / Auditor** — explicitly shared compliance/audit records
  (controlled access) plus the audit trail, with search.
- **Admin / System Administrator** — platform KPIs, user management
  (create/enable/disable), agent status, pending approvals, self-learning
  dashboard, and the full audit trail.

Access is **role-scoped**: every portal only sees the documents its role is
permitted to see (sensitivity ceiling + matter/client/parcel scope), and
only approver roles can decide gated actions.

## Configuration

The backend reads `config/settings.yaml`. In Docker you can override a few
things with environment variables (set in `docker-compose.yml`):

| Variable | Default | Purpose |
|---|---|---|
| `LFAE_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama host. Compose sets `http://ollama:11434`. |
| `LFAE_HOST` | `127.0.0.1` | Bind address. Compose sets `0.0.0.0`. |
| `LFAE_PORT` | `8000` | Port the app listens on. |
| `LFAE_CONFIG` | `config/settings.yaml` | Alternate settings file path. |

To use a different model, change `ollama.default_model` in
`config/settings.yaml` and pull that model (or add it to the `ollama-init`
command in `docker-compose.yml`).

## Data & persistence

- **`lfae_data`** volume → `/app/data`: the SQLite knowledge store, ingested
  documents, the append-only audit log, and the self-learning memory. This
  is what makes the platform "local-first" — delete the volume to reset.
- **`ollama_models`** volume → `/root/.ollama`: the pulled models.

To reset the platform's data:

```bash
docker compose down -v   # removes both volumes
docker compose up --build
```

## GPU (optional)

For GPU-accelerated inference, uncomment the `deploy.resources.reservations`
block under the `ollama` service in `docker-compose.yml` and make sure the
NVIDIA Container Toolkit is installed on the host.

## Running the frontend in dev mode (optional)

The Docker image builds the frontend for you. For local frontend
development with hot reload:

```bash
# terminal 1 — backend
python -m agent_platform.server          # serves API on :8000

# terminal 2 — frontend (proxies /api to :8000)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

The suite covers the 16-agent pipeline, the sensitivity/approval policy
engine, the self-learning engine, and the full multi-portal API (auth,
role-scoped data, request/upload/approve, admin user management).

## Security note

This is a **demo** build. The demo logins are public, sessions are bearer
tokens stored client-side, and there is no TLS or real identity provider.
For production you should:

- Replace the demo password map with real credentials (or SSO/OIDC).
- Terminate TLS at a reverse proxy (e.g. Caddy, nginx, or your load balancer).
- Keep the app and Ollama on a private network (remove the host port
  mappings in `docker-compose.yml`).
- Review the egress allowlist in `config/settings.yaml`.