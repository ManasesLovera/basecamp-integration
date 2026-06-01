.PHONY: install oauth app

install:
	uv sync

oauth:
	uvicorn oauth.main:app --port 8080 --reload

app:
	uvicorn app.main:app --port 8001 --reload
