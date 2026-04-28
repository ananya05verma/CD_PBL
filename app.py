from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from flask import render_template, redirect, url_for
from database import db, User, Conversion
from compiler_engine import process_input

app = Flask(__name__)

db_url = (
    os.environ.get("SQLALCHEMY_DATABASE_URI")
    or os.environ.get("DATABASE_URL")
    or "sqlite:///regexedu.db"
)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


with app.app_context():
    db.create_all()

# ------------------------
# PAGE ROUTES
# ------------------------

@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/logout")
def logout():
    return redirect(url_for("login_page"))
    
# --------------------------
# USER REGISTER
# --------------------------

@app.route("/register", methods=["POST"])
def register():

    data = request.json

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 400

    hashed_password = generate_password_hash(password)

    user = User(name=name, email=email, password=hashed_password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "User registered successfully",
        "user_id": user.id
    })


# --------------------------
# USER LOGIN
# --------------------------

@app.route("/login", methods=["POST"])
def login():

    data = request.json

    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid password"}), 401

    return jsonify({
        "message": "Login successful",
        "user_id": user.id
    })


# --------------------------
# PROCESS INPUT
# --------------------------

@app.route("/process", methods=["POST"])
def process():

    data = request.json

    text = data.get("text")
    mode = data.get("mode")
    user_id = data.get("user_id")

    try:

        result = process_input(text, mode)

        record = Conversion(
            user_id=user_id,
            mode=mode,
            input_text=text,
            tokens=str(result["tokens"]),
            ast=json.dumps(result["ast"])[:1000],
            regex=result["regex"],
            optimized_regex=result["optimized_regex"],
            classification=result["classification"]
        )

        db.session.add(record)
        db.session.commit()

        return jsonify(result)

    except Exception as e:

        return jsonify({"error": str(e)}), 400


# --------------------------
# USER HISTORY
# --------------------------

@app.route("/history/<int:user_id>")
def history(user_id):

    records = Conversion.query.filter_by(user_id=user_id).all()

    output = []

    for r in records:

        output.append({

            "input": r.input_text,
            "mode": r.mode,
            "regex": r.regex,
            "optimized_regex": r.optimized_regex,
            "classification": r.classification

        })

    return jsonify(output)


# --------------------------
# THEORY NOTES
# --------------------------

@app.route("/theory")
def theory():

    with open("theory_notes.json") as f:
        notes = json.load(f)

    return jsonify(notes)


# --------------------------
# RUN SERVER
# --------------------------

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "").strip() in ("1", "true", "True", "yes", "YES")
    app.run(debug=debug)