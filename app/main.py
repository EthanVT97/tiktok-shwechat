from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os, httpx
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Static files like /static/terms.html and privacy.html
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates like /templates/index.html
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
def login():
    params = {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "response_type": "code",
        "scope": "user.info.basic,video.list",  # ✅ video.list permission
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

@app.get("/me")
async def get_user_info(token: str):
    headers = {
        "Authorization": f"Bearer {token}"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://open.tiktokapis.com/v2/user/info/", headers=headers)
    return JSONResponse(content=resp.json())

@app.get("/videos")
async def get_user_videos(token: str):
    headers = {
        "Authorization": f"Bearer {token}"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://open.tiktokapis.com/v2/video/list/", headers=headers)
    return JSONResponse(content=resp.json())
