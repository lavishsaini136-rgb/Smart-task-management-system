# TaskFlow — Smart Task Management System

A full-stack Python web application built with Flask, PostgreSQL, Pandas/NumPy, WebSockets, and a clean HTML/CSS frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.0 |
| Database | PostgreSQL + psycopg2 |
| Analytics | Pandas, NumPy |
| Real-time | Flask-SocketIO (WebSockets) |
| Auth | Flask sessions + Werkzeug password hashing |
| Frontend | HTML5, CSS3, Vanilla JS |

---

## Features

- **Authentication** — Register, login, logout with hashed passwords
- **Task CRUD** — Create, read, update, delete tasks via REST API
- **Task Fields** — Title, description, priority (low/medium/high), status (pending/in_progress/completed), created date
- **Analytics** — Total tasks, completed, pending, in-progress, completion %, priority breakdown (powered by Pandas & NumPy)
- **WebSockets** — Real-time task updates broadcast to all connected clients instantly
- **Responsive UI** — Clean brutalist-inspired design, works on mobile and desktop

---

## Project Structure

```
task_manager/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── schema.sql          # PostgreSQL schema
├── .env.example        # Environment variable template
├── README.md
└── templates/
    ├── auth.html       # Login / Register page
    └── dashboard.html  # Main dashboard
```

---

## Setup Instructions

### 1. Prerequisites

- Python 3.10+
- PostgreSQL 14+

### 2. Clone & install

```bash
git clone <your-repo-url>
cd task_manager

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials and a strong SECRET_KEY
```

### 4. Set up PostgreSQL

```bash
# Create the database
createdb taskmanager

# Apply the schema
psql -d taskmanager -f schema.sql
```

### 5. Run the app

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

---

## REST API Reference

All task endpoints require an active session (login first).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/tasks` | Get all tasks for current user |
| POST | `/api/tasks` | Create a new task |
| PUT | `/api/tasks/<id>` | Update a task |
| DELETE | `/api/tasks/<id>` | Delete a task |
| GET | `/api/analytics` | Get analytics summary |

### Example: Create Task

```json
POST /api/tasks
{
  "title": "Build REST API",
  "description": "Implement CRUD endpoints",
  "priority": "high",
  "status": "in_progress"
}
```

---

## WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Server → Client | Connection confirmed |
| `task_update` | Server → Client | Broadcast on any task add/update/delete |
| `ping_server` | Client → Server | Heartbeat |
| `pong_server` | Server → Client | Heartbeat response |

---

## Analytics (Pandas & NumPy)

The `/api/analytics` endpoint uses Pandas DataFrames and NumPy to compute:

- `total` — count of all tasks
- `completed` — count with status = completed
- `pending` — count with status = pending
- `in_progress` — count with status = in_progress
- `completion_pct` — `np.round((completed / total) * 100, 2)`
- `priority_breakdown` — `value_counts()` per priority level

---

## Submission Checklist

- [x] GitHub Repository
- [x] Database Schema (`schema.sql`)
- [x] README with setup steps
- [ ] Demo Video (record a 2–3 min walkthrough)
