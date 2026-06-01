# Basecamp Integration

A FastAPI web app and CLI for managing Basecamp 4 projects, todolists, and todos via the [Basecamp API](https://github.com/basecamp/bc3-api).

## Setup

### 1. Register your app

Create an integration at [launchpad.37signals.com/integrations](https://launchpad.37signals.com/integrations). Set the redirect URI to `http://localhost:8080/oauth/callback`.

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Authorize with Basecamp

```bash
make oauth          # starts OAuth server on http://localhost:8080
```

Open `http://localhost:8080/oauth/start` in your browser, log in, and authorize. Tokens are saved to `.env` automatically. You can then stop the OAuth server.

### 5. Start the app

```bash
make app            # starts web app on http://localhost:8001
```

## Web App

Navigate to `http://localhost:8001` to browse your Basecamp projects, view todolists, create todolists and todos, and mark todos complete — all with inline HTMX updates.

## CLI

```bash
# List projects
basecamp-cli list-projects

# List todolists in a project
basecamp-cli list-todolists --project-id 12345678

# List todos in a todolist
basecamp-cli list-todos --project-id 12345678 --todolist-id 87654321
basecamp-cli list-todos --project-id 12345678 --todolist-id 87654321 --completed

# Create a todolist
basecamp-cli create-todolist --project-id 12345678 --name "Sprint 2"

# Create a single todo
basecamp-cli create-todo --project-id 12345678 --todolist-id 87654321 \
  --content "Write tests" --due 2024-03-01 --assignee 111222

# Mark a todo complete
basecamp-cli complete-todo --project-id 12345678 --todo-id 99887766

# Create a todolist with multiple todos from a template file
basecamp-cli create-from-template --project-id 12345678 --template-file template.example.yaml
```

### Template format

```yaml
name: "Sprint 1 Tasks"
description: "Optional description"
todos:
  - content: "Set up CI pipeline"
    due_on: "2024-02-01"
  - content: "Write unit tests"
  - content: "Review pull requests"
    due_on: "2024-02-05"
```

Both `.yaml`/`.yml` and `.json` formats are supported.

## Token Refresh

Access tokens are refreshed automatically when within 5 minutes of expiry. New tokens are written back to `.env`, so the file will be updated during normal operation.
