import asyncio
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv, set_key

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

LAUNCHPAD_TOKEN_URL = "https://launchpad.37signals.com/authorization/token"
BC3_BASE = "https://3.basecampapi.com"
USER_AGENT = "Basecamp Integration (contact@example.com)"


def _reload_env() -> None:
    load_dotenv(ENV_PATH, override=True)


def _is_token_expired() -> bool:
    expires_at = os.getenv("TOKEN_EXPIRES_AT")
    if not expires_at:
        return False
    try:
        expiry = datetime.fromisoformat(expires_at)
        return datetime.now(timezone.utc) >= expiry - timedelta(minutes=5)
    except ValueError:
        return False


class BasecampClient:
    def __init__(self):
        _reload_env()
        self._account_id = os.getenv("ACCOUNT_ID")
        self._base_url = f"{BC3_BASE}/{self._account_id}"
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._http = httpx.AsyncClient(base_url=self._base_url, headers={"User-Agent": USER_AGENT})
        await self._ensure_fresh_token()
        return self

    async def __aexit__(self, *_):
        if self._http:
            await self._http.aclose()

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {os.getenv('ACCESS_TOKEN')}"}

    async def _ensure_fresh_token(self) -> None:
        if _is_token_expired():
            await self._refresh_token()

    async def _refresh_token(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                LAUNCHPAD_TOKEN_URL,
                params={
                    "type": "refresh",
                    "client_id": os.getenv("CLIENT_ID"),
                    "client_secret": os.getenv("CLIENT_SECRET"),
                    "refresh_token": os.getenv("REFRESH_TOKEN"),
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            tokens = resp.json()

        expires_in = tokens.get("expires_in", 1209600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        for key, value in {
            "ACCESS_TOKEN": tokens["access_token"],
            "REFRESH_TOKEN": tokens["refresh_token"],
            "TOKEN_EXPIRES_AT": expires_at.isoformat(),
        }.items():
            set_key(str(ENV_PATH), key, value)
        _reload_env()

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        assert self._http is not None
        for attempt in range(3):
            resp = await self._http.get(path, params=params, headers=self._auth_headers())
            if resp.status_code == 401:
                await self._refresh_token()
                continue
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                await asyncio.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Failed after retries")

    async def _post(self, path: str, json: dict | None = None) -> dict | None:
        assert self._http is not None
        for attempt in range(3):
            resp = await self._http.post(path, json=json, headers=self._auth_headers())
            if resp.status_code == 401:
                await self._refresh_token()
                continue
            if resp.status_code == 429:
                await asyncio.sleep(int(resp.headers.get("Retry-After", "5")))
                continue
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Failed after retries")

    async def _put(self, path: str, json: dict) -> dict:
        assert self._http is not None
        for attempt in range(3):
            resp = await self._http.put(path, json=json, headers=self._auth_headers())
            if resp.status_code == 401:
                await self._refresh_token()
                continue
            if resp.status_code == 429:
                await asyncio.sleep(int(resp.headers.get("Retry-After", "5")))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Failed after retries")

    # --- Projects ---

    async def get_projects(self) -> list:
        return await self._get("/projects.json")  # type: ignore[return-value]

    async def get_project(self, project_id: int) -> dict:
        return await self._get(f"/projects/{project_id}.json")  # type: ignore[return-value]

    # --- Todosets ---

    async def get_todoset(self, project_id: int, todoset_id: int) -> dict:
        return await self._get(f"/buckets/{project_id}/todosets/{todoset_id}.json")  # type: ignore[return-value]

    # --- Todolists ---

    async def get_todolists(self, project_id: int, todoset_id: int) -> list:
        return await self._get(f"/buckets/{project_id}/todosets/{todoset_id}/todolists.json")  # type: ignore[return-value]

    async def get_todolist(self, project_id: int, todolist_id: int) -> dict:
        return await self._get(f"/buckets/{project_id}/todolists/{todolist_id}.json")  # type: ignore[return-value]

    async def create_todolist(self, project_id: int, todoset_id: int, name: str, description: str = "") -> dict:
        return await self._post(  # type: ignore[return-value]
            f"/buckets/{project_id}/todosets/{todoset_id}/todolists.json",
            json={"name": name, "description": description},
        )

    # --- Todos ---

    async def get_todos(self, project_id: int, todolist_id: int, completed: bool = False) -> list:
        params = {"completed": "true"} if completed else {}
        return await self._get(f"/buckets/{project_id}/todolists/{todolist_id}/todos.json", params=params)  # type: ignore[return-value]

    async def get_todo(self, project_id: int, todo_id: int) -> dict:
        return await self._get(f"/buckets/{project_id}/todos/{todo_id}.json")  # type: ignore[return-value]

    async def create_todo(
        self,
        project_id: int,
        todolist_id: int,
        content: str,
        description: str = "",
        assignee_ids: list[int] | None = None,
        due_on: str | None = None,
    ) -> dict:
        payload: dict = {"content": content}
        if description:
            payload["description"] = description
        if assignee_ids:
            payload["assignee_ids"] = assignee_ids
        if due_on:
            payload["due_on"] = due_on
        return await self._post(  # type: ignore[return-value]
            f"/buckets/{project_id}/todolists/{todolist_id}/todos.json",
            json=payload,
        )

    async def complete_todo(self, project_id: int, todo_id: int) -> None:
        await self._post(f"/buckets/{project_id}/todos/{todo_id}/completion.json")

    async def uncomplete_todo(self, project_id: int, todo_id: int) -> None:
        assert self._http is not None
        resp = await self._http.delete(
            f"/buckets/{project_id}/todos/{todo_id}/completion.json",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()

    async def create_todolist_from_template(
        self,
        project_id: int,
        todoset_id: int,
        name: str,
        todos: list[dict],
        description: str = "",
    ) -> dict:
        todolist = await self.create_todolist(project_id, todoset_id, name, description)
        todolist_id = todolist["id"]
        for todo in todos:
            await self.create_todo(
                project_id=project_id,
                todolist_id=todolist_id,
                content=todo["content"],
                description=todo.get("description", ""),
                due_on=todo.get("due_on"),
            )
        return todolist
