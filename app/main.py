from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import httpx
import os
from urllib.parse import urlencode
from secrets import token_urlsafe
from supabase import create_client, Client
import logging

# Load env variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("SUPABASE_URL or SUPABASE_KEY not set in environment variables.")
    raise RuntimeError("Missing Supabase configuration")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# FastAPI app instance
app = FastAPI()

# Import and include routers
from modules import real_estate
app.include_router(real_estate.router)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "changeme_secure_secret_should_be_long"),
    session_cookie="session",
    https_only=os.getenv("ENVIRONMENT") == "production"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# TikTok OAuth config getter
def get_tiktok_config():
    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI")
    if not (client_key and client_secret and redirect_uri):
        logger.error("TikTok OAuth config missing from environment variables")
        raise RuntimeError("TikTok OAuth environment variables missing")
    return {
        "client_key": client_key,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
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
    url = f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"
    return RedirectResponse(url)

@app.get("/callback")
async def callback(request: Request, code: str = None, state: str = None):
    # Validate OAuth state
    if not state or state != request.session.get("oauth_state"):
        logger.warning("Invalid or missing OAuth state parameter.")
        raise HTTPException(status_code=403, detail="Invalid OAuth state")

    if not code:
        logger.warning("No OAuth code received in callback.")
        raise HTTPException(status_code=400, detail="Missing code parameter")

    conf = get_tiktok_config()

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Exchange code for access token
        token_res = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": conf["client_key"],
                "client_secret": conf["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": conf["redirect_uri"]
            }
        )
        if token_res.status_code != 200:
            logger.error(f"Failed to get access token: {token_res.text}")
            raise HTTPException(status_code=token_res.status_code, detail="Failed to get access token")
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error(f"Access token missing in response: {token_data}")
            raise HTTPException(status_code=500, detail="Access token missing in response")
        request.session["access_token"] = access_token

        # Fetch user info
        user_res = await client.get(
            "https://open.tiktokapis.com/v2/user/info/",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "display_name,avatar_url,username,unique_id"}
        )
        if user_res.status_code != 200:
            logger.error(f"Failed to fetch user info: {user_res.text}")
            raise HTTPException(status_code=user_res.status_code, detail="Failed to fetch user info")

        user_data = user_res.json().get("data", {})
        if not user_data:
            logger.error(f"User data missing in response: {user_res.text}")
            raise HTTPException(status_code=500, detail="User data missing in response")

        request.session["user_info"] = user_data

        # Save or update user in Supabase (synchronously)
        unique_id = user_data.get("unique_id")
        if unique_id:
            try:
                result = supabase.table("users").select("id").eq("tiktok_id", unique_id).execute()
                if not result.data:
                    supabase.table("users").insert({
                        "tiktok_id": unique_id,
                        "username": user_data.get("username"),
                        "display_name": user_data.get("display_name"),
                        "avatar_url": user_data.get("avatar_url")
                    }).execute()
                else:
                    # Optional: update existing user info here if needed
                    pass
            except Exception as e:
                logger.error(f"Supabase DB error: {e}")

    return RedirectResponse("/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if "access_token" not in request.session:
        return RedirectResponse("/")
    user = request.session.get("user_info")
    services = [
        {"title": "Real Estate Bot", "description": "Buy/Sell properties in Yangon", "path": "/service/real-estate"},
        {"title": "Live Selling Toolkit", "description": "Sell live on TikTok", "path": "/service/live-selling"},
        {"title": "Delivery Bot", "description": "Auto track and notify deliveries", "path": "/service/delivery"},
        {"title": "AI Marketing", "description": "Generate content with AI", "path": "/service/ai-marketing"},
    ]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "services": services
    })

@app.get("/me")
async def me(request: Request):
    if "access_token" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"data": {"user": request.session.get("user_info")}}

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/service/{tool}", response_class=HTMLResponse)
async def tool_view(tool: str, request: Request):
    if "access_token" not in request.session:
        return RedirectResponse("/")
    user = request.session.get("user_info")
    tool_name_map = {
        "real-estate": "Real Estate Bot",
        "live-selling": "Live Selling Toolkit",
        "delivery": "Delivery Bot",
        "ai-marketing": "AI Marketing"
    }
    title = tool_name_map.get(tool, "Unknown Tool")
    return templates.TemplateResponse("tool.html", {
        "request": request,
        "user": user,
        "tool": tool,
        "tool_title": title
    })
