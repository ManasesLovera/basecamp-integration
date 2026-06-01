import asyncio
import os
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv

from oauth.token_store import load_tokens, save_tokens

load_dotenv()

LAUNCHPAD_TOKEN_URL = "https://launchpad.37signals.com/authorization/token"
BC3_BASE = "https://3.basecampapi.com"
USER_AGENT = "Basecamp Integration (contact@example.com)"


def _is_token_expired(tokens: dict) -> bool:
    expires_at = tokens.get("token_expires_at")
    if not expires_at:
        return False
    try:
        expiry = datetime.fromisoformat(expires_at)
        return datetime.now(timezone.utc) >= expiry - timedelta(minutes=5)
    except ValueError:
        return False


class BasecampClient:
    def __init__(self):
        self._tokens = load_tokens()
        self._account_id = self._tokens.get("account_id")
        self._base_url = f"{BC3_BASE}/{self._account_id}"
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        if _is_token_expired(self._tokens):
            await self._refresh_token()
        return self

    async def __aexit__(self, *_):
        if self._http:
            await self._http.aclose()

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._tokens['access_token']}"}

    async def _refresh_token(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                LAUNCHPAD_TOKEN_URL,
                params={
                    "type": "refresh",
                    "client_id": os.getenv("CLIENT_ID"),
                    "client_secret": os.getenv("CLIENT_SECRET"),
                    "refresh_token": self._tokens["refresh_token"],
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        save_tokens(
            data["access_token"],
            data["refresh_token"],
            data.get("expires_in", 1209600),
            self._tokens["account_id"],
        )
        self._tokens = load_tokens()

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Send a request, retrying on transient transport errors and 401/429."""
        assert self._http is not None
        for attempt in range(3):
            try:
                resp = await self._http.request(
                    method, path, headers=self._auth_headers(), **kwargs
                )
            except httpx.TransportError:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if resp.status_code == 401:
                await self._refresh_token()
                continue
            if resp.status_code == 429:
                await asyncio.sleep(int(resp.headers.get("Retry-After", "5")))
                continue
            return resp
        raise RuntimeError("Failed after retries")

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        resp = await self._send("GET", path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: dict | None = None) -> dict | None:
        resp = await self._send("POST", path, json=json)
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        return resp.json()

    async def _put(self, path: str, json: dict) -> dict:
        resp = await self._send("PUT", path, json=json)
        resp.raise_for_status()
        return resp.json()

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
        resp = await self._send("DELETE", f"/buckets/{project_id}/todos/{todo_id}/completion.json")
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
