# BookClub — AI201 Lab 5

A small reading-list app where club members track books, log progress, and view reading stats.

## Features

- **Book list** — shared reading list across all members
- **Reading tracker** — mark books as started or finished
- **Stats** — reading streak, books finished this month, total pages read

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
# or: .\.venv\Scripts\Activate.ps1   # Windows (PowerShell)

pip install -r requirements.txt

python seed_data.py   # create and populate the database
python app.py         # start server at http://127.0.0.1:5000
```

The seed script prints all three user IDs — keep them handy for testing.

## Running Tests

```bash
pytest tests/ -v
```

Uses an in-memory SQLite database; no seed data needed.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/books/` | List all books |
| `POST` | `/books/` | Add a book |
| `POST` | `/reading/start` | Mark a book as started |
| `POST` | `/reading/finish` | Mark a book as finished |
| `GET` | `/reading/current/<user_id>` | Books a user is currently reading |
| `GET` | `/reading/history/<user_id>` | Books a user has finished (most recent first) |
| `GET` | `/stats/<user_id>` | Reading streak, books this month, total pages |

## Codebase Structure

```
app.py                      Flask application factory
models.py                   SQLAlchemy models: User, Book, ReadingEvent
extensions.py               Shared db instance
routes/
  books.py                  Book list endpoints
  reading.py                Reading progress endpoints
  stats.py                  Statistics endpoint
services/
  reading_service.py        Reading list business logic
  stats_service.py          Statistics calculations (streak, pages, monthly count)
tests/
  test_services.py          Unit tests for service layer
seed_data.py                Database seed script
```

## Architecture

The app follows a three-layer architecture:

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Routes | `routes/` | Receive HTTP requests, call services, format responses |
| Services | `services/` | Business logic — calculations, rules, data transforms |
| Models | `models.py` | Database schema; no business logic |

## Example Requests

```bash
# List all books
curl http://127.0.0.1:5000/books/

# Get reading stats (replace USER_ID with output from seed_data.py)
curl http://127.0.0.1:5000/stats/USER_ID

# Get reading history
curl http://127.0.0.1:5000/reading/history/USER_ID

# Start reading a book
curl -X POST http://127.0.0.1:5000/reading/start \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "book_id": "BOOK_ID"}'

# Mark a book as finished
curl -X POST http://127.0.0.1:5000/reading/finish \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "book_id": "BOOK_ID"}'
```
