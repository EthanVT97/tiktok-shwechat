# modules/real_estate.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from supabase import create_client
from dotenv import dotenv_values

config = dotenv_values(".env")
supabase = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/service/real-estate", response_class=HTMLResponse)
async def real_estate_dashboard(request: Request):
    if "access_token" not in request.session:
        return RedirectResponse("/")
    user = request.session.get("user_info")
    return templates.TemplateResponse("real_estate_dashboard.html", {
        "request": request,
        "user": user,
    })


@router.get("/service/real-estate/listings", response_class=HTMLResponse)
async def list_properties(request: Request):
    if "access_token" not in request.session:
        return RedirectResponse("/")
    user = request.session.get("user_info")

    result = supabase.table("properties").select("*").eq("owner_id", user["unique_id"]).execute()
    listings = result.data or []

    return templates.TemplateResponse("real_estate_listings.html", {
        "request": request,
        "user": user,
        "listings": listings
    })
