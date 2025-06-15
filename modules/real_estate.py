# modules/real_estate.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/service/real-estate", response_class=HTMLResponse)
async def real_estate_dashboard(request: Request):
    user = request.session.get("user_info")
    return templates.TemplateResponse("real_estate_dashboard.html", {
        "request": request,
        "user": user,
        "title": "Yangon Real Estate Bot"
    })
