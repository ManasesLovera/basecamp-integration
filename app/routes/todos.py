from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.client import BasecampClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _todoset_id(project: dict) -> int:
    return next(t["id"] for t in project["dock"] if t["name"] == "todoset" and t["enabled"])


@router.get("/projects/{project_id}/todolists", response_class=HTMLResponse)
async def todolists_page(request: Request, project_id: int):
    async with BasecampClient() as bc:
        project = await bc.get_project(project_id)
        todolists = await bc.get_todolists(project_id, _todoset_id(project))
    return templates.TemplateResponse(
        request, "todolists.html",
        {"project": project, "todolists": todolists, "project_id": project_id},
    )


@router.post("/projects/{project_id}/todolists", response_class=HTMLResponse)
async def create_todolist(
    request: Request,
    project_id: int,
    name: str = Form(...),
    description: str = Form(""),
):
    async with BasecampClient() as bc:
        project = await bc.get_project(project_id)
        todolist = await bc.create_todolist(project_id, _todoset_id(project), name, description)
    return templates.TemplateResponse(
        request, "partials/todolist_row.html",
        {"project_id": project_id, "todolist": todolist},
    )


@router.get("/projects/{project_id}/todolists/{todolist_id}", response_class=HTMLResponse)
async def todos_page(request: Request, project_id: int, todolist_id: int):
    async with BasecampClient() as bc:
        project = await bc.get_project(project_id)
        todolist = await bc.get_todolist(project_id, todolist_id)
        todos = await bc.get_todos(project_id, todolist_id)
    return templates.TemplateResponse(
        request, "todos.html",
        {
            "project": project,
            "todolist": todolist,
            "todos": todos,
            "project_id": project_id,
            "todolist_id": todolist_id,
        },
    )


@router.post("/projects/{project_id}/todolists/{todolist_id}/todos", response_class=HTMLResponse)
async def create_todo(
    request: Request,
    project_id: int,
    todolist_id: int,
    content: str = Form(...),
    due_on: str = Form(""),
):
    async with BasecampClient() as bc:
        todo = await bc.create_todo(
            project_id=project_id,
            todolist_id=todolist_id,
            content=content,
            due_on=due_on or None,
        )
    return templates.TemplateResponse(
        request, "partials/todo_item.html",
        {"project_id": project_id, "todolist_id": todolist_id, "todo": todo},
    )


@router.post("/projects/{project_id}/todos/{todo_id}/complete", response_class=HTMLResponse)
async def complete_todo(request: Request, project_id: int, todo_id: int, todolist_id: int = 0):
    async with BasecampClient() as bc:
        await bc.complete_todo(project_id, todo_id)
        todo = await bc.get_todo(project_id, todo_id)
    return templates.TemplateResponse(
        request, "partials/todo_item.html",
        {"project_id": project_id, "todolist_id": todolist_id, "todo": todo},
    )
