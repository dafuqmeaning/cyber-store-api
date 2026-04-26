# Cyber Store API

FastAPI backend for the Cyber Store Telegram WebApp prototype.

## Run

```powershell
copy .env.example .env
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

## Configure

Set these values in `.env`:

- `TELEGRAM_BOT_TOKEN`
- `SESSION_SECRET`
- `ALLOW_DEMO_AUTH=false` for production

The SQLite database is created automatically on startup.
