# Telegram Business Archive

Private, self-hosted archive for messages Telegram delivers through the official Bot API Business Chat Automation integration. It uses no userbot, MTProto session, phone login, Telethon, or privacy bypass.

> **Security warning:** this database contains private conversations. Do not publish PostgreSQL, the API, backups, `ARCHIVE_API_KEY`, or bot token. Use HTTPS in production.

## Local startup

1. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` and a long random `ARCHIVE_API_KEY`.
2. Run `uv sync`, then `uv run alembic upgrade head`.
3. Run `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.
4. Open `http://localhost:8000/docs`.

Development-only polling is available with `uv run python -m app.telegram.polling`; production must use webhooks. Set `FRONTEND_ORIGIN` to the HTTPS Mini App origin and retain `MEDIA_PATH` on a Railway Volume when `MEDIA_STORAGE=local`.

## Mini App

The React Mini App lives in the sibling `../frontend` repository. It validates Telegram `initData` on every request and scopes data to the caller's active Business connections. Set `FRONTEND_ORIGIN=https://hang8s.github.io` for CORS and `MINI_APP_URL=https://hang8s.github.io/EYE_NEMO_FRONTEND/` for the bot button, then run `uv run python -m scripts.configure_mini_app`. Users can also send `/archive` to the bot.

Required settings are `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, and `ARCHIVE_API_KEY`. Production additionally requires `APP_ENV=production`, `TELEGRAM_MODE=webhook`, `APP_BASE_URL`, and `TELEGRAM_WEBHOOK_SECRET`. `MEDIA_STORAGE` accepts `none` (default) or `local`; attachment metadata is always retained. With `local`, the service downloads supported media to `MEDIA_PATH`; use a persistent volume in production.

## Telegram setup

1. Create a bot in **@BotFather** and save its token.
2. In BotFather, enable **Secretary Mode** for the bot. This is the current Telegram requirement for business chat automation.
3. Deploy this service over HTTPS and set `APP_BASE_URL` to its public root.
4. Run `uv run python -m scripts.set_webhook`.
5. In Telegram, open **Settings → Telegram Business → Chatbots / Chat Automation → Connect Bot**, choose the bot and explicitly choose its recipients and permissions.

Telegram availability depends on the account/product features shown by Telegram. The bot only receives messages Telegram officially sends for the connection; it cannot read historical, secret, view-once, self-destructing, or unselected chats.

## API

All `/api/*` routes require `Authorization: Bearer $ARCHIVE_API_KEY`.

- `GET /api/chats`, `GET /api/chats/{chat_id}`
- `GET /api/chats/{chat_id}/messages`
- `GET /api/messages/{message_id}`
- `GET /api/search?q=oauth`
- `GET /api/stats`
- public `GET /health`, `GET /health/ready`

Examples:

```sh
curl -H "Authorization: Bearer $ARCHIVE_API_KEY" https://domain.com/api/chats
curl -H "Authorization: Bearer $ARCHIVE_API_KEY" "https://domain.com/api/search?q=oauth"
curl -H "Authorization: Bearer $ARCHIVE_API_KEY" "https://domain.com/api/chats/<id>/messages?limit=50"
```

Search currently uses portable, parameterized PostgreSQL `ILIKE` across text and captions. The models preserve edit versions, reply identity, deletion state, normalized sender/chat metadata, and media metadata.

## Railway

Create a Railway project, add PostgreSQL and an app service from this repository. Use [`.env.railway.example`](.env.railway.example) as the backend service's Variables checklist. Replace every placeholder with a real value. Set `DATABASE_URL` to an async PostgreSQL URL beginning with `postgresql+asyncpg://`; `FRONTEND_ORIGIN` for GitHub Pages is `https://hang8s.github.io` (without the repository path). Set `APP_BASE_URL` to the public Railway backend URL. Railway supplies `PORT`, which the Docker command honors; do not set `APP_PORT` there.

After deployment, run `uv run alembic upgrade head`, `uv run python -m scripts.set_webhook`, and `uv run python -m scripts.configure_mini_app` in the backend service environment. In the frontend GitHub repository, set the Actions variable `VITE_API_BASE_URL` to the Railway backend URL and rerun the Pages workflow. A 512 MB instance and small PostgreSQL plan are sufficient for a low-volume MVP; increase database disk according to retained media/history.

## Validation

Run `uv run ruff check .`, `uv run mypy app`, and `uv run pytest`. The official Bot API event names used here are `business_connection`, `business_message`, `edited_business_message`, and `deleted_business_messages`.
