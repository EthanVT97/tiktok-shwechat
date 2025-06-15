# ShweChat 🤝 TikTok OAuth Integration Platform

> **Production-ready full-stack TikTok login + business tool UI built for Myanmar** 🇲🇲

![ShweChat Logo](https://raw.githubusercontent.com/EthanVT97/tiktok-shwechat/main/static/shwechat_logo.png)

---

## 📌 Features

- 🛂 Secure TikTok OAuth 2.0 flow with `state` validation
- 🧠 Frontend + Backend communication via `access_token`
- ⚙️ FastAPI backend + HTML/Tailwind frontend
- 💬 Myanmar Unicode-ready font support
- 🔒 HTTPS, secure cookies, session protection
- 📦 Ready for deployment to Render, Netlify, or Docker

---

## 📁 Project Structure

```bash
shwechat/
├── main.py                  # FastAPI backend with OAuth routes
├── templates/
│   └── index.html           # Login UI with animated components
├── static/                  # Optional for storing assets
├── .env                     # Environment variables (not committed)
├── requirements.txt         # Python dependencies
├── Dockerfile               # (optional) Containerized backend
└── README.md
```

---

## ⚙️ Requirements

- Python 3.10+
- `fastapi`, `httpx`, `jinja2`, `uvicorn`, `python-dotenv`

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Configuration (.env)

```env
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret
TIKTOK_REDIRECT_URI=https://your-domain.com/callback
SESSION_SECRET=replace_with_strong_key
ENVIRONMENT=production
```

> For development, set `ENVIRONMENT=dev` to disable HTTPS-only mode

---

## 🚀 Run Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open browser to: [http://localhost:8000](http://localhost:8000)

---

## 🧪 OAuth Flow

1. `/login` → Redirects user to TikTok OAuth with `state`
2. `/callback` → TikTok redirects back with `code`
3. `/callback?code=...&state=...` → exchanges token
4. `/me?token=...` → fetches TikTok user info


---

## 🛡️ Security Considerations

- CSRF mitigation via `state` token
- Secrets stored securely in `.env`
- Session protection using `SessionMiddleware`
- Secure cookie with `https_only`
- Frontend fetch uses `application/json` headers

---

## 📦 Deployment Options

### ▶️ Render.com

- Add your `.env` values in the Render Dashboard
- Use the following `start` command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

### 🐳 Docker

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t shwechat .
docker run -p 8000:8000 --env-file .env shwechat
```

---

## 🧠 Future Add-ons

- `dashboard.html` for post-login interface
- tiering & campaign UI
- Telegram bot integration
- Auto token refresh system

---

## 🤝 Credits

Developed by **Ethan** Myanmar
> Inspired by 🇲🇲 businesse 


