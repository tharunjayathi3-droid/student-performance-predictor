"""
Student Performance Prediction System
Flask + scikit-learn web app.
Updated feature set:
  study_hours, sleep_hours, screen_time, sports_hours,
  other_activities, attendance, previous_marks
"""
import os
import io
import pickle
import json
import sqlite3
from functools import wraps
from datetime import datetime

import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

# Optional PDF export
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "model.pkl")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-change-me")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1")
DB_PATH = os.path.join(BASE_DIR, "data", "platform.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS game_attempts (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), score INTEGER NOT NULL, total INTEGER NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS bookmarks (user_id INTEGER NOT NULL REFERENCES users(id), resource_id TEXT NOT NULL, PRIMARY KEY(user_id, resource_id))")

init_db()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"error": "Please sign in to continue."}), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

# ── Load (or train) model on startup ────────────────────────────────────────
def load_model():
    if not os.path.exists(MODEL_PATH):
        from train_model import train_and_save
        train_and_save()
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)

MODEL = load_model()

# Updated feature order — must match train_model.py exactly
FEATURE_ORDER = [
    "study_hours", "sleep_hours", "screen_time",
    "sports_hours", "other_activities", "attendance", "previous_marks",
]


# ── Helpers ──────────────────────────────────────────────────────────────────
def classify(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 60:
        return "Average"
    return "Needs Improvement"


def success_probability(score: float, target: float) -> float:
    gap  = score - target
    prob = 1 / (1 + np.exp(-gap / 6))
    return float(np.clip(prob * 100, 1, 99))


def time_recommendations(payload: dict) -> list:
    recs = []

    # Screen time
    if payload["screen_time"] > 3:
        cut = round(payload["screen_time"] - 2, 1)
        recs.append(
            f"Reduce screen time by {cut} hour(s) per day — "
            "consider using app timers or focus-mode tools."
        )

    # Study hours
    if payload["study_hours"] < 6:
        add = round(6 - payload["study_hours"], 1)
        recs.append(
            f"Add {add} more study hour(s) daily — "
            "try the Pomodoro technique for focused sessions."
        )

    # Sleep
    if payload["sleep_hours"] > 9:
        recs.append(
            f"You sleep {payload['sleep_hours']}h — aim for 7-8 h; "
            "oversleeping can reduce alertness during study."
        )
    elif payload["sleep_hours"] < 6:
        recs.append(
            "Increase sleep to at least 7 hours; "
            "sleep deprivation significantly impairs memory retention."
        )

    # Sports / physical activity
    if payload["sports_hours"] < 0.5:
        recs.append(
            "Add at least 30 minutes of physical activity daily — "
            "exercise improves concentration and reduces stress."
        )
    elif payload["sports_hours"] > 3:
        recs.append(
            f"Physical activity is great! With {payload['sports_hours']}h/day, "
            "ensure it doesn't cut into core study time."
        )

    # Attendance
    if payload["attendance"] < 80:
        recs.append(
            f"Attendance is {payload['attendance']}% — "
            "raise it above 80% to avoid missing key concepts."
        )

    # Other activities
    if payload["other_activities"] > 3:
        cut = round(payload["other_activities"] - 2, 1)
        recs.append(
            f"Other activities take {payload['other_activities']}h/day — "
            f"try trimming {cut}h to reclaim study time."
        )

    if not recs:
        recs.append("Your routine looks great — keep it consistent and stay hydrated!")

    # Always include one positive habit tip
    recs.append(
        "Review your notes within 24 hours of class — spaced repetition "
        "boosts long-term retention by up to 80%."
    )
    return recs


def generate_timetable(payload: dict, target: float) -> list:
    extra_study = max(0, 6 - payload["study_hours"])
    has_sports  = payload["sports_hours"] >= 0.5

    timetable = [
        {"time": "06:00 AM", "activity": "Wake up & freshen up"},
        {"time": "06:30 AM", "activity": "Morning Exercise / Yoga" if not has_sports else "Morning Walk / Warm-up"},
        {"time": "07:00 AM", "activity": "Revision — hardest subject of the day"},
        {"time": "09:00 AM", "activity": "College / Classes"},
        {"time": "05:00 PM", "activity": "Break & healthy snack"},
        {"time": "06:00 PM", "activity": f"Focused Study Session ({2 + round(extra_study)}h)"},
        {"time": "08:00 PM", "activity": "Dinner & Family Time"},
        {"time": "09:00 PM", "activity": "Assignments & Practice Problems"},
        {"time": "10:30 PM", "activity": "Light Reading / Reflection"},
        {"time": "11:00 PM", "activity": "Sleep (7-8 h recommended)"},
    ]

    if has_sports:
        timetable.insert(6, {
            "time": "05:30 PM",
            "activity": f"Sports / Physical Activity ({payload['sports_hours']}h)"
        })

    if payload["screen_time"] > 3:
        timetable.insert(-1, {
            "time": "10:00 PM",
            "activity": "Screen-free wind-down — avoid phone/TV 1h before bed"
        })

    return timetable


def goal_analysis(predicted: float, target: float, payload: dict) -> str:
    diff = target - predicted
    if diff <= 0:
        return (
            f"You're on track to exceed your goal of {target}%! "
            "Maintain consistency and keep challenging yourself."
        )
    extra_study  = round(diff / 4, 1)
    reduce_screen = round(min(payload["screen_time"], diff / 5), 1)
    sports_note   = (
        " Adding daily physical activity will also help."
        if payload["sports_hours"] < 0.5 else ""
    )
    return (
        f"You need approximately {extra_study} additional study hour(s) daily "
        f"and reducing screen time by {reduce_screen}h would help bridge the "
        f"gap to your target of {target}%.{sports_note}"
    )


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:80]
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        if not name or "@" not in email or len(password) < 10:
            flash("Enter your name, a valid email, and a password with at least 10 characters.", "error")
        else:
            try:
                with db() as conn:
                    conn.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)", (name,email,generate_password_hash(password),datetime.utcnow().isoformat()))
                flash("Account created. Sign in to continue.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            return redirect(url_for("index"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/learn/<page>")
@login_required
def learning_page(page):
    pages = {"home", "subjects", "materials", "recommendations", "game", "progress", "profile", "ml-insights"}
    if page not in pages:
        return "Not found", 404
    with db() as conn:
        attempts = conn.execute("SELECT score,total,created_at FROM game_attempts WHERE user_id=? ORDER BY id DESC LIMIT 20", (session["user_id"],)).fetchall()
        bookmarks = {row[0] for row in conn.execute("SELECT resource_id FROM bookmarks WHERE user_id=?", (session["user_id"],))}
    metrics_path = os.path.join(BASE_DIR, "model", "metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path) as metrics_file:
            metrics = json.load(metrics_file)
    else:
        metrics = None
    return render_template("learning.html", page=page, name=session.get("name", "Student"), attempts=[dict(a) for a in attempts], bookmarks=bookmarks, metrics=metrics)

@app.route("/api/game-attempt", methods=["POST"])
@login_required
def save_game_attempt():
    data = request.get_json(silent=True) or {}
    try:
        score, total = int(data.get("score")), int(data.get("total"))
    except (TypeError, ValueError):
        return jsonify({"error": "Score and total must be whole numbers."}), 400
    if total < 1 or total > 100 or score < 0 or score > total:
        return jsonify({"error": "Score must be between zero and the question total."}), 400
    with db() as conn:
        conn.execute("INSERT INTO game_attempts(user_id,score,total,created_at) VALUES(?,?,?,?)", (session["user_id"],score,total,datetime.utcnow().isoformat()))
    return jsonify({"saved": True})

@app.route("/api/bookmark", methods=["POST"])
@login_required
def toggle_bookmark():
    resource_id = str((request.get_json(silent=True) or {}).get("resource_id", ""))[:80]
    if not resource_id:
        return jsonify({"error": "Resource id is required."}), 400
    with db() as conn:
        found = conn.execute("SELECT 1 FROM bookmarks WHERE user_id=? AND resource_id=?", (session["user_id"],resource_id)).fetchone()
        if found:
            conn.execute("DELETE FROM bookmarks WHERE user_id=? AND resource_id=?", (session["user_id"],resource_id))
            saved = False
        else:
            conn.execute("INSERT INTO bookmarks(user_id,resource_id) VALUES(?,?)", (session["user_id"],resource_id))
            saved = True
    return jsonify({"saved": saved})


@app.route("/predict", methods=["POST"])
@login_required
def predict():
    data = request.get_json(silent=True) or {}
    try:
        payload = {k: float(data.get(k, 0)) for k in FEATURE_ORDER}
        target  = float(data.get("target_goal", 80))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input — all fields must be numbers."}), 400
    limits = {"study_hours": (0, 16), "sleep_hours": (0, 24), "screen_time": (0, 24), "sports_hours": (0, 12), "other_activities": (0, 24), "attendance": (0, 100), "previous_marks": (0, 100)}
    for key, (low, high) in limits.items():
        if not low <= payload[key] <= high:
            return jsonify({"error": f"{key.replace('_', ' ').title()} must be between {low} and {high}."}), 400
    if not 0 <= target <= 100:
        return jsonify({"error": "Target must be between 0 and 100."}), 400

    x     = np.array([[payload[k] for k in FEATURE_ORDER]])
    score = float(np.clip(MODEL.predict(x)[0], 0, 100))
    sgpa  = round(min(10.0, score / 9.5), 2)
    level = classify(score)
    prob  = round(success_probability(score, target), 1)

    return jsonify({
        "predicted_score":   round(score, 1),
        "predicted_sgpa":    sgpa,
        "level":             level,
        "success_probability": prob,
        "target":            target,
        "recommendations":   time_recommendations(payload),
        "timetable":         generate_timetable(payload, target),
        "goal_analysis":     goal_analysis(score, target, payload),
        "inputs":            payload,
    })


@app.route("/report", methods=["POST"])
@login_required
def report():
    if not HAS_REPORTLAB:
        return jsonify({"error": "PDF export not available on this deployment."}), 500

    data = request.get_json(force=True)
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4, title="Student Performance Report")
    styles = getSampleStyleSheet()
    flow   = []

    flow.append(Paragraph("Student Performance Report", styles["Title"]))
    flow.append(Paragraph(datetime.now().strftime("%B %d, %Y"), styles["Normal"]))
    flow.append(Spacer(1, 16))

    for line in [
        f"<b>Predicted Score:</b> {data.get('predicted_score')}%",
        f"<b>Predicted SGPA:</b> {data.get('predicted_sgpa')}",
        f"<b>Performance Level:</b> {data.get('level')}",
        f"<b>Success Probability:</b> {data.get('success_probability')}%",
        f"<b>Target:</b> {data.get('target')}%",
    ]:
        flow.append(Paragraph(line, styles["Normal"]))
    flow.append(Spacer(1, 12))

    flow.append(Paragraph("<b>Goal Analysis</b>", styles["Heading2"]))
    flow.append(Paragraph(data.get("goal_analysis", ""), styles["Normal"]))
    flow.append(Spacer(1, 12))

    flow.append(Paragraph("<b>Recommendations</b>", styles["Heading2"]))
    for r in data.get("recommendations", []):
        flow.append(Paragraph(f"• {r}", styles["Normal"]))
    flow.append(Spacer(1, 12))

    flow.append(Paragraph("<b>Personalized Timetable</b>", styles["Heading2"]))
    rows  = [["Time", "Activity"]] + [
        [t["time"], t["activity"]] for t in data.get("timetable", [])
    ]
    table = Table(rows, colWidths=[100, 350])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    flow.append(table)

    doc.build(flow)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name="performance_report.pdf")


@app.route("/health")
def health():
    return {"status": "ok", "features": FEATURE_ORDER}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)
