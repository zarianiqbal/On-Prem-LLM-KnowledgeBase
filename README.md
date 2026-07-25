# On-Prem LLM Knowledge Base

A privacy-first, self-hosted RAG (Retrieval-Augmented Generation) knowledge base.
Employees ask questions in natural language and get answers drawn **only** from
company documents their role is allowed to see. Everything runs on your own
hardware — documents, embeddings, and the LLM never leave the machine.

> **The core security idea:** the LLM never touches raw data. It only ever sees
> small, relevant chunks that the retrieval layer has already filtered by the
> requesting user's role. Access control happens in the database query, _before_
> the LLM is involved — so a user in `hr` can never trigger retrieval of
> `finance`-tagged content.

---

## How it works

```
                    ┌──────────────┐
   Browser  ───────►│  React (Vite)│   login • chat • admin upload
                    └──────┬───────┘
                           │  /api  (JWT in header)
                    ┌──────▼───────┐
                    │   FastAPI    │
                    │              │
   ask ───────────► │ 1. verify JWT → user roles
                    │ 2. embed the question (local model)
                    │ 3. vector search  ── ACL filter by role ──┐
                    │ 4. build prompt from allowed chunks       │
                    │ 5. call Ollama, stream answer back        │
                    └──────┬───────────────────────┬────────────┘
                           │                        │
                  ┌────────▼────────┐      ┌────────▼────────┐
                  │ Postgres +      │      │ Ollama (local   │
                  │ pgvector        │      │ LLM on your GPU)│
                  │ chunks + roles  │      └─────────────────┘
                  └─────────────────┘
```

A question flows through: **embed → ACL-filtered vector search → prompt → Ollama → stream**.
A document flows through: **parse (PDF/DOCX/txt) → chunk → embed → store with role tags**.

## Tech stack

| Layer        | Choice                                                    |
| ------------ | --------------------------------------------------------- |
| Frontend     | React + Vite (plain JSX/CSS), Axios                        |
| Backend      | FastAPI (Python 3.12), SQLAlchemy 2                        |
| Vector store | Postgres + [pgvector](https://github.com/pgvector/pgvector)|
| Embeddings   | `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim)      |
| LLM          | [Ollama](https://ollama.com) (e.g. Llama 3.1) — local GPU |
| Auth         | JWT; dev role-login now, Google OAuth stub for production  |

---

## Prerequisites

- **Python 3.11+** and **Node.js 18+**
- **Ollama** — install from [ollama.com](https://ollama.com), then pull a model:
  ```bash
  ollama pull llama3.1
  ollama serve            # runs the API at http://localhost:11434
  ```
- **Postgres with pgvector** — easiest via Docker (below). No Docker? Install
  Postgres natively and add the pgvector extension.

---

## Quick start

### 1. Database

With Docker:
```bash
docker compose up -d db          # Postgres + pgvector on localhost:5432
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # then edit JWT_SECRET etc.
uvicorn app.main:app --reload    # http://localhost:8000
```

The first request that needs embeddings will download the model (~90 MB) once.
Interactive API docs live at http://localhost:8000/docs.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Open http://localhost:5173. Log in with the dev login (pick an email + roles;
keep **Admin** checked so you can upload). Go to **Admin**, upload a document and
tag it with roles (e.g. `hr`), then head to **Chat** and ask a question.

### Everything in Docker (optional)

`docker compose up` starts both Postgres and the backend. Ollama still runs on
the host for GPU access; the backend reaches it via `host.docker.internal`.

---

## Roles & access tiers

Roles are just free-text tags — each company invents whatever fits their org
(`hr`, `finance`, `partners`, `clinical`, …). They control what the chatbot is
allowed to **retrieve** for a user, not who can upload (that's the separate
`is_admin` flag).

- **Document tags** decide who can see a document's content. Tag with specific
  roles (`hr,finance`) to restrict it; leave **untagged** to make it public to
  every authenticated user.
- **A user with no roles is a `customer`** — the least-privileged tier. They see
  only public (untagged) documents plus anything explicitly tagged `customer`.
  They never see staff-tagged content. (The default role name is configurable
  via `DEFAULT_ROLE`.)
- **Admins** (`is_admin`) can upload/delete documents, manage users, and bypass
  ACL filtering.

> To keep something away from customers, tag it with a staff role. Untagged ==
> public by design, so don't upload sensitive files without a tag.

---

## Testing the access-control model

1. Upload `salaries.pdf` tagged `finance`, and `handbook.pdf` tagged `hr`.
2. Log in with roles `hr` (uncheck Admin) → ask about salaries → the model has no
   finance chunks to answer from.
3. Log in with roles `finance` → the same question now returns an answer with a
   citation. The chunks were filtered in SQL; the LLM never saw the other file.
4. Log in with **no roles** (customer tier) → you see neither file, only public
   (untagged) documents. This is the least-privileged default.

---

## Project structure

```
On-Prem-LLM-KnowledgeBase/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + route wiring
│   │   ├── config.py          # settings from .env
│   │   ├── database.py        # engine, session, pgvector init
│   │   ├── models.py          # User / Document / Chunk (+ ACL column)
│   │   ├── schemas.py         # request/response models
│   │   ├── auth.py            # JWT + current-user dependency + user upsert
│   │   ├── oauth.py           # Google OAuth client (Authlib)
│   │   ├── embeddings.py      # local sentence-transformers wrapper
│   │   ├── ingest.py          # parse → chunk → embed → store
│   │   ├── retrieval.py       # ACL-filtered vector search  ← security core
│   │   ├── ollama_client.py   # prompt building + streaming
│   │   └── routers/           # auth, documents, chat, users endpoints
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  # React + Vite app
│   └── src/
│       ├── api.js             # axios client + streaming helper
│       ├── App.jsx            # routing + auth state
│       └── pages/             # Login, Chat, Admin
├── docker-compose.yml         # Postgres (pgvector) + backend
└── README.md
```

---

## Roadmap

- [x] ACL-filtered RAG core (ingest, retrieve, generate)
- [x] Dev role-based auth + JWT
- [x] Chat UI with streaming answers and citations
- [x] Admin document upload with per-role access tags
- [x] Customer default tier for users with no roles (least privilege)
- [ ] Google OAuth login
- [ ] Auto-map Workspace groups → roles (Admin SDK, needs domain-wide delegation)
- [ ] Google Drive sync (watch a shared folder, auto-ingest changes)
- [ ] Audit logging (who asked what, which chunks were returned)
- [ ] Prompt-injection hardening + rate limiting + HTTPS via Nginx

## Security notes

- Never commit `.env`. Generate a strong `JWT_SECRET`
  (`python -c "import secrets; print(secrets.token_hex(32))"`).
- Set `DEV_AUTH_ENABLED=false` in production once Google OAuth is wired up —
  otherwise anyone can mint a token with any role.
- The system prompt instructs the model to treat retrieved context as data, not
  commands, as a first line of defense against prompt injection in documents.

## License

MIT — see `LICENSE`.
