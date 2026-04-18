import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
from sklearn.neighbors import KNeighborsClassifier
import pandas as pd

app = Flask(__name__)
app.secret_key = "abutalha123secret"

GEMINI_API_KEY = "AIzaSyCv_1PivKdBcKrBLUb1xN8UG7J99Xq89pw"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

training_data = [[25,1,2,0,0],[22,1,5,0,0],[47,3,15,1,1],[52,3,20,1,1],[46,2,12,1,0],[56,3,25,1,1],[18,1,1,0,0],[24,1,3,0,0],[35,2,10,1,0],[40,3,18,1,1]]
labels = ["NO","NO","YES","YES","YES","YES","NO","NO","YES","YES"]
ml_model = KNeighborsClassifier()
ml_model.fit(training_data, labels)

job_map = {"student":1,"employee":2,"business":3,"doctor":3,"engineer":3,"teacher":2,"other":1}

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE, password_hash TEXT, age INTEGER DEFAULT 0, job TEXT DEFAULT 'other')""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS contact_messages (id INTEGER PRIMARY KEY, name TEXT, email TEXT, subject TEXT, message TEXT)""")
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def logged_in():
    return "user_id" in session

init_db()

@app.route("/")
def home():
    return render_template("home.html", logged_in=logged_in())

@app.route("/about")
def about():
    return render_template("about.html", logged_in=logged_in())

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if not all([name, email, subject, message]):
            flash("All fields are required.", "error")
            return render_template("contact.html", logged_in=logged_in())
        conn = get_db()
        conn.execute("INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)", (name, email, subject, message))
        conn.commit()
        conn.close()
        flash("Your message has been sent!", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html", logged_in=logged_in())

@app.route("/register", methods=["GET", "POST"])
def register():
    if logged_in():
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        age = int(request.form.get("age", 0))
        job = request.form.get("job", "other")
        if not all([username, email, password, confirm]):
            flash("All fields are required.", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, email, password_hash, age, job) VALUES (?, ?, ?, ?, ?)", (username, email, generate_password_hash(password), age, job))
            conn.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except:
            flash("Username or email already exists.", "error")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if logged_in():
        return redirect(url_for("home"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT id, username, email, password_hash, age, job FROM users WHERE username = ? OR email = ?", (identifier, identifier)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["age"] = user["age"] if user["age"] else 0
            session["job"] = user["job"] if user["job"] else "other"
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials. Please try again.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/chatbot")
def chatbot():
    if not logged_in():
        flash("Please log in to use the AI Chatbot.", "info")
        return redirect(url_for("login"))
    return render_template("chatbot.html", username=session.get("username"), logged_in=True)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    user_message = (data or {}).get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    system_prompt = "You are AbuTalha's professional AI assistant on his website AbuTalha.pythonanywhere.com. About AbuTalha: He is a professional Web Developer and Python Programmer. He has a company with 500 workers. He offers web development, Python programming, AI integration and database services. He is based in Karachi, Pakistan. Services: Building professional websites, Python and Flask web applications, AI chatbot integration, Database design, Machine Learning solutions. Contact: Visit the Contact page. Your job: Answer customer questions professionally and helpfully. Answer in the same language the customer uses. Keep answers short and clear. Customer message: " + user_message
    payload = {"contents": [{"parts": [{"text": system_prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}}
    try:
        response = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        reply = result["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/predict", methods=["GET", "POST"])
def predict():
    prediction = None
    user_age = session.get("age", 0)
    user_job = session.get("job", "other")
    job_score = job_map.get(user_job, 1)
    if request.method == "POST":
        pages = int(request.form.get("pages", 0))
        minutes = int(request.form.get("minutes", 0))
        clicked_contact = int(request.form.get("clicked_contact", 0))
        visited_before = int(request.form.get("visited_before", 0))
        prediction = ml_model.predict([[user_age, job_score, pages, minutes, clicked_contact]])[0]
    return render_template("predict.html", prediction=prediction, logged_in=logged_in(), user_age=user_age, user_job=user_job)

@app.route("/admin")
def admin():
    if not logged_in():
        return redirect(url_for("login"))
    conn = get_db()
    messages = conn.execute("SELECT * FROM contact_messages").fetchall()
    try:
        users = conn.execute("SELECT id, username, email, age, job FROM users").fetchall()
    except:
        users = conn.execute("SELECT id, username, email FROM users").fetchall()
    conn.close()
    files = os.listdir(UPLOAD_FOLDER)
    return render_template("admin.html", messages=messages, users=users, files=files)

@app.route("/report")
def report():
    if not logged_in():
        return redirect(url_for("login"))
    conn = get_db()
    try:
        users = conn.execute("SELECT username, age, job FROM users").fetchall()
    except:
        users = []
    messages = conn.execute("SELECT * FROM contact_messages").fetchall()
    conn.close()
    if len(users) > 0:
        df = pd.DataFrame([dict(u) for u in users])
        total_users = len(df)
        avg_age = round(df["age"].mean(), 1) if "age" in df.columns else 0
        min_age = int(df["age"].min()) if "age" in df.columns else 0
        max_age = int(df["age"].max()) if "age" in df.columns else 0
        jobs = df["job"].value_counts().to_dict() if "job" in df.columns else {}
    else:
        total_users = 0
        avg_age = 0
        min_age = 0
        max_age = 0
        jobs = {}
    total_messages = len(messages)
    return render_template("report.html", total_users=total_users, avg_age=avg_age, min_age=min_age, max_age=max_age, jobs=jobs, total_messages=total_messages, users=users, logged_in=logged_in())

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not logged_in():
        return redirect(url_for("login"))
    uploaded = None
    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                uploaded = filename
    files = os.listdir(UPLOAD_FOLDER)
    return render_template("upload.html", files=files, uploaded=uploaded, logged_in=logged_in())

@app.route("/download/<filename>")
def download_file(filename):
    if not logged_in():
        return redirect(url_for("login"))
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route("/view/<filename>")
def view_file(filename):
    if not logged_in():
        return redirect(url_for("login"))
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "AbuTalha Developer", "short_name": "AbuTalha", "description": "AbuTalha Developer Website with AI Chatbot", "start_url": "/", "display": "standalone", "background_color": "#222222", "theme_color": "#333333"})

# =====================
# NEW — PORTFOLIO PAGE
# =====================
@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html", logged_in=logged_in())

if __name__ == "__main__":
    app.run(debug=True)
