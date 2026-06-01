from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.client import BasecampClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with BasecampClient() as bc:
        projects = await bc.get_projects()
    return templates.TemplateResponse("projects.html", {"request": request, "projects": projects})
