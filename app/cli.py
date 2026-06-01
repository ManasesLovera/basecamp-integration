import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlencode

import click
import yaml
from dotenv import load_dotenv

from app.client import BasecampClient

load_dotenv()


def run(coro):
    return asyncio.run(coro)


@click.group()
def cli():
    """Basecamp CLI — manage todos, todolists, and projects."""


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@cli.command("auth-url")
def auth_url():
    """Print the Basecamp OAuth authorization URL to open in a browser."""
    client_id = os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise click.UsageError("CLIENT_ID and REDIRECT_URI must be set in .env")
    params = urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri})
    click.echo(f"https://launchpad.37signals.com/authorization/new?{params}")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@cli.command("list-projects")
def list_projects():
    """List all active Basecamp projects."""
    async def _run():
        async with BasecampClient() as bc:
            projects = await bc.get_projects()
        click.echo(f"{'ID':<12} {'Name'}")
        click.echo("-" * 50)
        for p in projects:
            click.echo(f"{p['id']:<12} {p['name']}")

    run(_run())


# ---------------------------------------------------------------------------
# Todolists
# ---------------------------------------------------------------------------

@cli.command("list-todolists")
@click.option("--project-id", required=True, type=int, help="Basecamp project ID")
def list_todolists(project_id: int):
    """List all todolists in a project."""
    async def _run():
        async with BasecampClient() as bc:
            project = await bc.get_project(project_id)
            todoset = next(
                t for t in project["dock"] if t["name"] == "todoset" and t["enabled"]
            )
            todolists = await bc.get_todolists(project_id, todoset["id"])
        click.echo(f"{'ID':<12} {'Name'}")
        click.echo("-" * 50)
        for tl in todolists:
            click.echo(f"{tl['id']:<12} {tl['title']}")

    run(_run())


@cli.command("create-todolist")
@click.option("--project-id", required=True, type=int)
@click.option("--name", required=True)
@click.option("--description", default="")
def create_todolist(project_id: int, name: str, description: str):
    """Create a new todolist in a project."""
    async def _run():
        async with BasecampClient() as bc:
            project = await bc.get_project(project_id)
            todoset = next(
                t for t in project["dock"] if t["name"] == "todoset" and t["enabled"]
            )
            result = await bc.create_todolist(project_id, todoset["id"], name, description)
        click.echo(f"Created todolist '{result['title']}' (ID: {result['id']})")

    run(_run())


# ---------------------------------------------------------------------------
# Todos
# ---------------------------------------------------------------------------

@cli.command("list-todos")
@click.option("--project-id", required=True, type=int)
@click.option("--todolist-id", required=True, type=int)
@click.option("--completed", is_flag=True, default=False, help="Show completed todos")
def list_todos(project_id: int, todolist_id: int, completed: bool):
    """List todos in a todolist."""
    async def _run():
        async with BasecampClient() as bc:
            todos = await bc.get_todos(project_id, todolist_id, completed=completed)
        click.echo(f"{'ID':<12} {'Done':<6} {'Content'}")
        click.echo("-" * 60)
        for t in todos:
            done = "✓" if t.get("completed") else " "
            click.echo(f"{t['id']:<12} {done:<6} {t['content']}")

    run(_run())


@cli.command("create-todo")
@click.option("--project-id", required=True, type=int)
@click.option("--todolist-id", required=True, type=int)
@click.option("--content", required=True, help="Todo task description")
@click.option("--description", default="", help="Rich text description")
@click.option("--due", default=None, metavar="YYYY-MM-DD", help="Due date")
@click.option("--assignee", multiple=True, type=int, help="Assignee person ID (repeatable)")
def create_todo(project_id: int, todolist_id: int, content: str, description: str, due: str | None, assignee: tuple):
    """Create a new todo item."""
    async def _run():
        async with BasecampClient() as bc:
            result = await bc.create_todo(
                project_id=project_id,
                todolist_id=todolist_id,
                content=content,
                description=description,
                assignee_ids=list(assignee) if assignee else None,
                due_on=due,
            )
        click.echo(f"Created todo '{result['content']}' (ID: {result['id']})")

    run(_run())


@cli.command("complete-todo")
@click.option("--project-id", required=True, type=int)
@click.option("--todo-id", required=True, type=int)
def complete_todo(project_id: int, todo_id: int):
    """Mark a todo as complete."""
    async def _run():
        async with BasecampClient() as bc:
            await bc.complete_todo(project_id, todo_id)
        click.echo(f"Todo {todo_id} marked as complete.")

    run(_run())


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@cli.command("create-from-template")
@click.option("--project-id", required=True, type=int)
@click.option(
    "--template-file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="YAML or JSON file defining the todolist template",
)
def create_from_template(project_id: int, template_file: Path):
    """Create a todolist with todos from a YAML/JSON template file.

    Template format:
      name: "Sprint 1 Tasks"
      description: "Optional description"
      todos:
        - content: "Set up CI pipeline"
          due_on: "2024-02-01"
        - content: "Write tests"
    """
    raw = template_file.read_text()
    if template_file.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)

    name = data.get("name")
    if not name:
        raise click.UsageError("Template must have a 'name' field.")

    todos = data.get("todos", [])

    async def _run():
        async with BasecampClient() as bc:
            project = await bc.get_project(project_id)
            todoset = next(
                t for t in project["dock"] if t["name"] == "todoset" and t["enabled"]
            )
            result = await bc.create_todolist_from_template(
                project_id=project_id,
                todoset_id=todoset["id"],
                name=name,
                todos=todos,
                description=data.get("description", ""),
            )
        click.echo(f"Created todolist '{result['title']}' (ID: {result['id']}) with {len(todos)} todo(s).")

    run(_run())
