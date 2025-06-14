from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
import os, httpx
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/")
def root():
    return {"msg": "ShweChat TikTok Login Active ✅"}

@app.get("/login")
def login():
    params = {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "response_type": "code",
        "scope": "user.info.basic",
        "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI"),
        "state": "shwe123"
    }
    return RedirectResponse(f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}")

@app.get("/callback")
async def callback(code: str, state: str):
    async with httpx.AsyncClient() as client:
        token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        data = {
            "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
            "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI")
        }
        resp = await client.post(token_url, data=data)
        token_data = resp.json()
    return JSONResponse(content=token_data)
