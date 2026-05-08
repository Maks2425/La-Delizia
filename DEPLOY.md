# Deploy La-Delizia

## 1) Prepare environment variables

Use `.env.example` as a template and set at least:

- `SECRET_KEY` - long random string for Flask sessions.
- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- `PORT` - provided by platform (Render/Railway usually inject this automatically).
- `SESSION_COOKIE_SECURE=1` (for HTTPS production).
- MySQL vars (`MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`) if you use DB.
- Optional: `OPENAI_API_KEY`, `OPENAI_MODEL`.

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

## 3) Start in production

Use Gunicorn:

```bash
gunicorn --bind 0.0.0.0:$PORT wsgi:app
```

`Procfile` is included, so many PaaS providers detect this command automatically.

## 4) Deploy to Render / Railway (quick setup)

1. Connect your GitHub repository.
2. Create a **Web Service**.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn --bind 0.0.0.0:$PORT wsgi:app`
5. Add all environment variables from step 1.
6. Deploy.

## 5) Notes about storage

This app writes files to local folders (`carts/`, `orders/`, `bookings/`, `local_users.json`).
On many cloud platforms local disk can be ephemeral. For reliable production, move this data to a database or persistent volume.

