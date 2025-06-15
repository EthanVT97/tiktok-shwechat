from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os
import httpx
from urllib.parse import urlencode
from dotenv import load_dotenv
from secrets import token_urlsafe
from typing import Optional

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# ======================
# Middleware Configuration
# ======================
if not os.getenv("SESSION_SECRET"):
    raise RuntimeError("SESSION_SECRET must be set in .env")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    session_cookie="shwechat_session",
    https_only=True if os.getenv("ENVIRONMENT") == "production" else False
)

if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["tiktok-shwechat.onrender.com"]
    )

# ======================
# Static Files & Templates
# ======================
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ======================
# Helper Functions
# ======================
def get_tiktok_client():
    config = {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI")
    }
    if not all(config.values()):
        raise RuntimeError("Missing TikTok OAuth configuration")
    return config

# ======================
# Routes
# ======================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    tiktok_config = get_tiktok_client()
    state = token_urlsafe(16)
    request.session["oauth_state"] = state

    params = {
        "client_key": tiktok_config["client_key"],
        "response_type": "code",
        "scope": "user.info.basic,video.list",
        "redirect_uri": tiktok_config["redirect_uri"],
        "state": state
    }
    return RedirectResponse(f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}")

@app.api_route("/callback", methods=["GET", "POST"])
async def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    if error:
        return JSONResponse({"error": error}, status_code=400)

    if request.method == "POST":
        form_data = await request.form()
        code = code or form_data.get("code")
        state = state or form_data.get("state")

    if not code:
        return JSONResponse({"error": "Authorization code missing"}, status_code=400)

    if state != request.session.get("oauth_state"):
        return JSONResponse({"error": "Invalid state parameter"}, status_code=403)

    try:
        tiktok_config = get_tiktok_client()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": tiktok_config["client_key"],
                    "client_secret": tiktok_config["client_secret"],
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": tiktok_config["redirect_uri"]
                }
            )
            response.raise_for_status()
            token_data = response.json()

            request.session.update({
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in")
            })

            if "application/json" in request.headers.get("accept", ""):
                return JSONResponse(token_data)

            return RedirectResponse(url="/dashboard")

    except httpx.HTTPStatusError as e:
        return JSONResponse({
            "error": "Token exchange failed",
            "details": str(e),
            "response": e.response.json() if e.response else None
        }, status_code=500)

@app.get("/me")
async def me(token: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://open.tiktokapis.com/v2/user/info/",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "avatar_url,display_name,username,unique_id"}
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if "access_token" not in request.session:
        return RedirectResponse(url="/")

    if "user_info" not in request.session:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://open.tiktokapis.com/v2/user/info/",
                    headers={"Authorization": f"Bearer {request.session['access_token']}"},
                    params={"fields": "display_name,avatar_url"}
                )
                response.raise_for_status()
                request.session["user_info"] = response.json().get("data", {})
        except Exception:
            pass

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": request.session.get("user_info", {})
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# ======================
# Startup Configuration
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
    
