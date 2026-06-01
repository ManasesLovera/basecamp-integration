.PHONY: install oauth app

install:
	uv sync

oauth:
	uv run uvicorn oauth.main:app --port 8080 --reload

app:
	uv run uvicorn app.main:app --port 8001 --reload
