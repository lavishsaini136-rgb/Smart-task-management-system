from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*")

# ─── Database Connection ───────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "taskmanager"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed')),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


# ─── Auth Decorator ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ─── Page Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login")
def login_page():
    return render_template("auth.html", mode="login")

@app.route("/register")
def register_page():
    return render_template("auth.html", mode="register")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))


# ─── Auth API ─────────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id, username",
            (username, email, generate_password_hash(password)),
        )
        user = cur.fetchone()
        conn.commit()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return jsonify({"message": "Registered successfully", "username": user["username"]}), 201
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "Username or email already exists"}), 409
    finally:
        cur.close()
        conn.close()


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"message": "Logged in", "username": user["username"]})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# ─── Task API ─────────────────────────────────────────────────────────────────

@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC",
        (session["user_id"],),
    )
    tasks = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    # Serialize datetimes
    for t in tasks:
        t["created_at"] = t["created_at"].isoformat()
        t["updated_at"] = t["updated_at"].isoformat()
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json()
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO tasks (user_id, title, description, priority, status)
           VALUES (%s, %s, %s, %s, %s) RETURNING *""",
        (
            session["user_id"],
            title,
            data.get("description", ""),
            data.get("priority", "medium"),
            data.get("status", "pending"),
        ),
    )
    task = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    task["created_at"] = task["created_at"].isoformat()
    task["updated_at"] = task["updated_at"].isoformat()

    socketio.emit("task_update", {"action": "added", "task": task})
    return jsonify(task), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    data = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """UPDATE tasks SET title=%s, description=%s, priority=%s, status=%s, updated_at=NOW()
           WHERE id=%s AND user_id=%s RETURNING *""",
        (
            data.get("title"),
            data.get("description"),
            data.get("priority"),
            data.get("status"),
            task_id,
            session["user_id"],
        ),
    )
    task = cur.fetchone()
    if not task:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404
    task = dict(task)
    conn.commit()
    cur.close()
    conn.close()
    task["created_at"] = task["created_at"].isoformat()
    task["updated_at"] = task["updated_at"].isoformat()

    socketio.emit("task_update", {"action": "updated", "task": task})
    return jsonify(task)


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM tasks WHERE id=%s AND user_id=%s RETURNING id",
        (task_id, session["user_id"]),
    )
    deleted = cur.fetchone()
    if not deleted:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "Task not found"}), 404
    conn.commit()
    cur.close()
    conn.close()

    socketio.emit("task_update", {"action": "deleted", "task_id": task_id})
    return jsonify({"message": "Task deleted"})


# ─── Analytics API ────────────────────────────────────────────────────────────

@app.route("/api/analytics", methods=["GET"])
@login_required
def analytics():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE user_id = %s", (session["user_id"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return jsonify({
            "total": 0, "completed": 0, "pending": 0, "in_progress": 0,
            "completion_pct": 0.0, "priority_breakdown": {},
            "avg_completion_rate": 0.0,
        })

    df = pd.DataFrame([dict(r) for r in rows])

    total = int(len(df))
    completed = int((df["status"] == "completed").sum())
    pending = int((df["status"] == "pending").sum())
    in_progress = int((df["status"] == "in_progress").sum())
    completion_pct = float(np.round((completed / total) * 100, 2)) if total else 0.0
    priority_breakdown = df["priority"].value_counts().to_dict()
    priority_breakdown = {k: int(v) for k, v in priority_breakdown.items()}

    return jsonify({
        "total": total,
        "completed": completed,
        "pending": pending,
        "in_progress": in_progress,
        "completion_pct": completion_pct,
        "priority_breakdown": priority_breakdown,
    })


# ─── WebSocket Events ─────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    emit("connected", {"message": "Real-time connection established"})


@socketio.on("ping_server")
def on_ping():
    emit("pong_server", {"time": datetime.utcnow().isoformat()})


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
