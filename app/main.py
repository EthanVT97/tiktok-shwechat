from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
app.add_middleware(GZipMiddleware)
app.add_middleware(HTTPSRedirectMiddleware)  # Force HTTPS in production
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=[
        "tiktok-shwechat.onrender.com",
        "localhost",
        "127.0.0.1"
    ]
)

# Session middleware for state management
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "default-secret-key-change-in-production"),
    session_cookie="shwechat_session",
    https_only=True if os.getenv("ENVIRONMENT") == "production" else False
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
    return {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI")
    }

# ======================
# Routes
# ======================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Homepage with login button"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    """Initiate TikTok OAuth flow"""
    tiktok_config = get_tiktok_client()
    
    # Generate and store CSRF state token
    state = token_urlsafe(16)
    request.session["oauth_state"] = state
    
    params = {
        "client_key": tiktok_config["client_key"],
        "response_type": "code",
        "scope": "user.info.basic,video.list",
        "redirect_uri": tiktok_config["redirect_uri"],
        "state": state
    }
    
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"
    return RedirectResponse(auth_url)

@app.get("/callback")
async def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """Handle TikTok OAuth callback"""
    tiktok_config = get_tiktok_client()
    
    # Check for errors from TikTok
    if error:
        return JSONResponse(
            {"error": error, "description": error_description},
            status_code=400
        )
    
    # Validate state parameter
    if state != request.session.get("oauth_state"):
        raise HTTPException(
            status_code=403,
            detail="Invalid state parameter - possible CSRF attempt"
        )
    
    # Ensure we have an authorization code
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code"
        )
    
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_url = "https://open.tiktokapis.com/v2/oauth/token/"
            data = {
                "client_key": tiktok_config["client_key"],
                "client_secret": tiktok_config["client_secret"],
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": tiktok_config["redirect_uri"]
            }
            
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            # Store tokens securely in session
            request.session.update({
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in")
            })
            
            return RedirectResponse(url="/dashboard")
            
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            {
                "error": "Token exchange failed",
                "details": str(e),
                "tiktok_response": e.response.json()
            },
            status_code=e.response.status_code
        )

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Protected dashboard page"""
    if "access_token" not in request.session:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": request.session.get("user_info")
        }
    )

@app.get("/api/me")
async def get_user_info(request: Request):
    """Get current user info from TikTok"""
    if "access_token" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        headers = {
            "Authorization": f"Bearer {request.session['access_token']}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://open.tiktokapis.com/v2/user/info/",
                headers=headers,
                params={"fields": "open_id,union_id,avatar_url,display_name"}
            )
            response.raise_for_status()
            
            user_data = response.json()
            request.session["user_info"] = user_data.get("data", {})
            
            return JSONResponse(user_data)
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Failed to fetch user info from TikTok"
        )

@app.get("/api/videos")
async def get_user_videos(request: Request):
    """Get user's videos from TikTok"""
    if "access_token" not in request.session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        headers = {
            "Authorization": f"Bearer {request.session['access_token']}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/video/list/",
                headers=headers,
                json={
                    "max_count": 20,
                    "cursor": 0
                }
            )
            response.raise_for_status()
            
            return JSONResponse(response.json())
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Failed to fetch videos from TikTok"
        )

@app.get("/logout")
async def logout(request: Request):
    """Clear session and log out"""
    request.session.clear()
    return RedirectResponse(url="/")

# ======================
# Error Handlers
# ======================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

# ======================
# Startup Event
# ======================
@app.on_event("startup")
async def startup():
    # Verify required environment variables
    required_vars = ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")
