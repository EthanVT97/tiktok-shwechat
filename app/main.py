from fastapi import FastAPI, Request, HTTPException 
from fastapi.responses import RedirectResponse, HTMLResponse 
from fastapi.templating import Jinja2Templates 
from fastapi.staticfiles import StaticFiles 
from starlette.middleware.sessions import SessionMiddleware 
from dotenv import load_dotenv import httpx import os 
from urllib.parse import urlencode 
from secrets import token_urlsafe 
from supabase import create_client, Client

Load environment variables

load_dotenv()

Supabase setup

SUPABASE_URL = os.getenv("SUPABASE_URL") SUPABASE_KEY = os.getenv("SUPABASE_KEY") supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FastAPI app

app = FastAPI()

Middleware

app.add_middleware( SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "changeme"), session_cookie="session", https_only=os.getenv("ENVIRONMENT") == "production" )

Static & Templates

app.mount("/static", StaticFiles(directory="static"), name="static") templates = Jinja2Templates(directory="templates")

def get_tiktok_config(): return { "client_key": os.getenv("TIKTOK_CLIENT_KEY"), "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"), "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI") }

@app.get("/") async def index(request: Request): return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login") async def login(request: Request): conf = get_tiktok_config() state = token_urlsafe(16) request.session["oauth_state"] = state params = { "client_key": conf["client_key"], "response_type": "code", "scope": "user.info.basic", "redirect_uri": conf["redirect_uri"], "state": state } return RedirectResponse(f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}")

@app.get("/callback") async def callback(request: Request, code: str = None, state: str = None): if state != request.session.get("oauth_state"): raise HTTPException(status_code=403, detail="Invalid state") conf = get_tiktok_config() async with httpx.AsyncClient() as client: # Exchange code for access token token_res = await client.post("https://open.tiktokapis.com/v2/oauth/token/", data={ "client_key": conf["client_key"], "client_secret": conf["client_secret"], "code": code, "grant_type": "authorization_code", "redirect_uri": conf["redirect_uri"] }) token_data = token_res.json() access_token = token_data.get("access_token") request.session["access_token"] = access_token

# Get user info from TikTok
    user_res = await client.get("https://open.tiktokapis.com/v2/user/info/", headers={
        "Authorization": f"Bearer {access_token}"
    }, params={"fields": "display_name,avatar_url,username,unique_id"})
    user_data = user_res.json().get("data", {})
    request.session["user_info"] = user_data

    # Sync user to Supabase
    unique_id = user_data.get("unique_id")
    if unique_id:
        result = supabase.table("users").select("id").eq("tiktok_id", unique_id).execute()
        if not result.data:
            supabase.table("users").insert({
                "tiktok_id": unique_id,
                "username": user_data.get("username"),
                "display_name": user_data.get("display_name"),
                "avatar_url": user_data.get("avatar_url")
            }).execute()

return RedirectResponse("/dashboard")

@app.get("/dashboard", response_class=HTMLResponse) async def dashboard(request: Request): if "access_token" not in request.session: return RedirectResponse("/") user = request.session.get("user_info") services = [ {"title": "Real Estate Bot", "description": "Buy/Sell properties in Yangon", "path": "/service/real-estate"}, {"title": "Live Selling Toolkit", "description": "Sell live on TikTok", "path": "/service/live-selling"}, {"title": "Delivery Bot", "description": "Auto track and notify deliveries", "path": "/service/delivery"}, {"title": "AI Marketing", "description": "Generate content with AI", "path": "/service/ai-marketing"}, ] return templates.TemplateResponse("dashboard.html", { "request": request, "user": user, "services": services })

@app.get("/me") async def me(request: Request): if "access_token" not in request.session: raise HTTPException(status_code=401, detail="Not authenticated") return {"data": {"user": request.session.get("user_info")}}

@app.get("/logout") async def logout(request: Request): request.session.clear() return RedirectResponse("/")

@app.get("/service/{tool}", response_class=HTMLResponse) async def tool_view(tool: str, request: Request): if "access_token" not in request.session: return RedirectResponse("/") user = request.session.get("user_info") tool_name_map = { "real-estate": "Real Estate Bot", "live-selling": "Live Selling Toolkit", "delivery": "Delivery Bot", "ai-marketing": "AI Marketing" } title = tool_name_map.get(tool, "Unknown Tool") return templates.TemplateResponse("tool.html", { "request": request, "user": user, "tool": tool, "tool_title": title })

