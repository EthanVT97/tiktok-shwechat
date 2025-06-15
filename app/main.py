from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import httpx
import os
from urllib.parse import urlencode
from secrets import token_urlsafe

load_dotenv()
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "changeme"),
    session_cookie="session",
    https_only=os.getenv("ENVIRONMENT") == "production"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_tiktok_config():
    return {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI")
    }

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    conf = get_tiktok_config()
    state = token_urlsafe(16)
    request.session["oauth_state"] = state
    params = {
        "client_key": conf["client_key"],
        "response_type": "code",
        "scope": "user.info.basic",
        "redirect_uri": conf["redirect_uri"],
        "state": state
    }
    return RedirectResponse(f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}")

@app.get("/callback")
async def callback(request: Request, code: str = None, state: str = None):
    if state != request.session.get("oauth_state"):
        raise HTTPException(status_code=403, detail="Invalid state")
    conf = get_tiktok_config()
    async with httpx.AsyncClient() as client:
        token_res = await client.post("https://open.tiktokapis.com/v2/oauth/token/", data={
            "client_key": conf["client_key"],
            "client_secret": conf["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": conf["redirect_uri"]
        })
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        request.session["access_token"] = access_token

        user_res = await client.get("https://open.tiktokapis.com/v2/user/info/", headers={
            "Authorization": f"Bearer {access_token}"
        }, params={"fields": "display_name,avatar_url,username,unique_id"})
        request.session["user_info"] = user_res.json().get("data", {})
    return RedirectResponse("/")

@app.get("/me")
async def me(request: Request):
    if "access_token" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"data": {"user": request.session.get("user_info")}}

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
