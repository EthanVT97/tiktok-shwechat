from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
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
# Basic Configuration
# ======================
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ======================
# Helper Functions
# ======================
def get_tiktok_client():
    """Get TikTok OAuth credentials from environment"""
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
    
    if not all(tiktok_config.values()):
        raise HTTPException(status_code=500, detail="TikTok client not configured")
    
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
    error: Optional[str] = None
):
    """Handle TikTok OAuth callback"""
    # Error handling
    if error:
        return JSONResponse({"error": error}, status_code=400)
    
    if not code:
        return JSONResponse({"error": "Authorization code missing"}, status_code=400)
    
    # State validation
    if state != request.session.get("oauth_state"):
        return JSONResponse({"error": "Invalid state parameter"}, status_code=403)
    
    # Token exchange
    try:
        tiktok_config = get_tiktok_client()
        async with httpx.AsyncClient() as client:
            token_url = "https://open.tiktokapis.com/v2/oauth/token/"
            data = {
                "client_key": tiktok_config["client_key"],
                "client_secret": tiktok_config["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": tiktok_config["redirect_uri"]
            }
            
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            # Store tokens in session
            request.session.update({
                "access_token": token_data.get("access_token"),
                "user_info": None  # Will be fetched when needed
            })
            
            return RedirectResponse(url="/dashboard")
            
    except httpx.HTTPStatusError as e:
        return JSONResponse({
            "error": "Token exchange failed",
            "details": str(e)
        }, status_code=500)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Protected dashboard page"""
    if "access_token" not in request.session:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": request.session.get("user_info")
    })

@app.get("/logout")
async def logout(request: Request):
    """Clear session and log out"""
    request.session.clear()
    return RedirectResponse(url="/")

# ======================
# Startup Configuration
# ======================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
