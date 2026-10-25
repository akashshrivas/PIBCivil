# UPSCByte

<p align="center"><img src="frontend/public/logo.png" alt="UPSCByte logo" width="120" /></p>

**UPSCByte** is a smarter UPSC preparation platform. It is being built as one
home for everything an aspirant needs, with more features added over time.

## Features

| Feature | Status | What it does |
|---|---|---|
| **PIBCivil** (Current Affairs) | Live (in progress) | Brings PIB, The Hindu and other sources into one place and gives the aspirant a quick overview of what matters for the exam |
| PYQs | Planned | Previous year questions, organised and searchable |
| Tests | Planned | Practice tests and analysis |
| More smart tools | Planned | Further solutions to make preparation smarter |

## Repo layout

- `pipeline/` - data ingestion and processing (PIB today, more sources later)
- `backend/` - FastAPI API
- `frontend/` - Next.js web app
- `scripts/` - R2 sync and Supabase insert helpers
- `docs/` - architecture and progress notes

See `docs/architecture.md` for details.
