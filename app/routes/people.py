from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.client import BasecampClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/people", response_class=HTMLResponse)
async def people_page(request: Request):
    async with BasecampClient() as bc:
        people = await bc.get_people()
    return templates.TemplateResponse(request, "people.html", {"people": people})
