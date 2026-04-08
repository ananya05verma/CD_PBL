from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversions = db.relationship(
        "Conversion",
        backref="user",
        lazy=True
    )


class Conversion(db.Model):

    __tablename__ = "conversions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    mode = db.Column(db.String(20))

    input_text = db.Column(db.Text)

    tokens = db.Column(db.Text)

    ast = db.Column(db.Text)

    regex = db.Column(db.Text)

    optimized_regex = db.Column(db.Text)

    classification = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)