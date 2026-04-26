# VoxCoach Frontend Demo

This is the Next.js frontend for the LAHacks demo.

## Run Locally

Start the backend first from the repo root:

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv sync --reinstall
uv run uvicorn backend.sprint.api:app --reload --reload-dir backend --host 0.0.0.0 --port 8000
```

Then start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

The frontend uses:

- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_WS_URL=ws://localhost:8000`

For local demo defaults, the app falls back to these URLs automatically. If you need different hosts or ports, copy `frontend/.env.example` to `frontend/.env.local` and edit the values.

Use the repo-local `uv run` command above rather than a globally installed `python` or `uvicorn`, otherwise Windows may resolve the wrong interpreter and miss project-only dependencies such as `google-genai`.

## Checks

```powershell
npm run lint
npm run build
```
