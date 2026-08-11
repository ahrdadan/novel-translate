# Novel Translation Application

This project is separated into two main components:

1. **`app/`** - The Backend API (FastAPI) responsible for novel translation jobs, managing database, and LLM integrations.
2. **`sample-client/`** - The Client Application (Python scripts) that interacts with the backend API to queue jobs, fetch translations, and process novel files.

## Getting Started

### Backend (`app/`)
To run the backend, navigate to the `app` folder:
```bash
cd app
uv run uvicorn src.main:app --reload --port 8000
```
*(Or use `make start` if available)*

### Client (`sample-client/`)
To run the client, navigate to the `sample-client` folder:
```bash
cd sample-client
uv run python main.py
```

Please see the respective folders for more detailed `README.md` files or configurations.
