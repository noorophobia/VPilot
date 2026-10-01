# VPilot MVP

Text-based AI receptionist demo for **Sunrise Family Clinic**: FAQ answers, availability checks, and validated appointment booking.

## Prerequisites

- PostgreSQL via Docker (optional; SQLite works out of the box for local MVP)
- Python 3.11+
- Node.js 18+
- A hosted Qwen-compatible inference API with a valid API key

## Required environment variables

Create a file named `.env` inside the `backend` folder. Use the variables below:

```env
DATABASE_URL=sqlite:///./vpilot.db
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

For local development, you can use SQLite. For Vercel production, use a persistent PostgreSQL database and set the values in the Vercel project environment settings.

Do not put the API key in the React frontend. The frontend only calls the FastAPI backend.

## Local setup

1. **Backend**

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
python seed.py
uvicorn main:app --reload --port 8000
```

2. **Frontend**

```bash
cd frontend
npm install
# Windows PowerShell: Copy-Item .env.example .env
# macOS/Linux: cp .env.example .env
npm run dev
```

The frontend `.env` sets `VITE_API_URL=http://localhost:8000` for local development. Vite reads this variable when it starts, so restart the dev server after changing it.

Open http://localhost:5173

## Production setup (Vercel)

1. Create a Vercel project for the backend and set its **Root Directory** to `backend`. Vercel recognizes `main.py` as the FastAPI entrypoint and installs dependencies from `backend/requirements.txt`; no Node `package.json`, `app.listen()`, or custom server is needed for the API.
2. Add these environment variables to the Vercel backend project (Production, and Preview if needed):
   - `DATABASE_URL`
   - `LLM_API_KEY`
   - `LLM_BASE_URL`
   - `LLM_MODEL`
   - `FRONTEND_ORIGINS` — exact public frontend origin(s), comma-separated
3. Set `DATABASE_URL` to a persistent PostgreSQL connection string using the `postgresql+psycopg://` driver prefix. Do not use the default SQLite file for Vercel.
4. Set the frontend project’s `VITE_API_URL` to the deployed backend URL, with no trailing slash, then redeploy the frontend.
5. Deploy. Vercel sets `VERCEL=1`; the backend now fails early with an actionable message if the database is still configured as SQLite.
6. Keep `LLM_API_KEY` only in the backend Vercel project. Never add it to the frontend project or a `VITE_` variable.

## OpenAI-compatible hosted Qwen API

VPilot expects a standard OpenAI-compatible chat completion endpoint from the backend:

- `LLM_BASE_URL` points to the provider base URL, for example `https://api.provider.example/v1`
- `LLM_MODEL` is the model name supported by that provider
- `LLM_API_KEY` is sent from the backend only
- The backend uses the OpenAI Python client with `client.chat.completions.create(...)`

This keeps the app compatible with hosted Qwen models that expose an OpenAI-compatible API.

## Demo scenarios

| Scenario | Example message |
|----------|-----------------|
| FAQ | What are the clinic hours? |
| Availability | Is Dr. Ahmed available tomorrow at 3 PM? |
| Booking | Book Dr. Ahmed tomorrow at 3 PM for Noor. |
| Missing info | Book me an appointment. |
| Unavailable slot | Try booking Dr. Ahmed tomorrow at 3 PM (seed data marks it taken). |
| Safety | Ask something not in the FAQ; VPilot should not invent details. |

## API

- `POST /chat` — agent conversation (used by the UI)
- `GET /availability?doctor_name=&date=YYYY-MM-DD&time=15:00`
- `POST /appointments` — direct booking (validated; agent uses internal tools)
- `GET /health`

## Notes

- Appointments are only confirmed after a successful database write.
- Tool arguments are validated in Python; the LLM never runs SQL directly.
- Voice (Whisper/Piper) is intentionally not included in this MVP layer.
- No Ollama or localhost model dependency is required for production deployment.
