from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file

from flask_login import login_required, current_user, login_user, logout_user # pip install flask-login

from LaDelizia_db import Session, Users, Menu, Orders, Reservation
from flask_login import LoginManager
from datetime import datetime

import os
import uuid
import json
import random

import secrets

app = Flask(__name__)

FILES_PATH = 'static/menu'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['MAX_FORM_MEMORY_SIZE'] = 1024 * 1024  # 1MB
app.config['MAX_FORM_PARTS'] = 500

app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

app.config['SECRET_KEY'] = '#cv)3v7w$*s3fk;5c!@y0?:?№3"9)#'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.query(Users).filter_by(id = user_id).first()
        if user:
            return user

@app.after_request
def apply_csp(response):
    nonce = secrets.token_urlsafe(16)  # Генеруємо випадковий nonce для дозволених скриптів
    csp = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self'; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.set_cookie('nonce', nonce)
    return response

@app.route('/')
@app.route('/home')
def home():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)

    dishes = load_dishes_from_json()
    reviews = generate_random_reviews(6)

    return render_template(
        'home.html',
        dishes=dishes,
        reviews=reviews
    )


def load_dishes_from_json():
    with open('menu.json', 'r', encoding='utf-8') as file:
        menu_data = json.load(file)

    dishes = []
    categories = menu_data.get('menu', {})

    for category_items in categories.values():
        for dish in category_items:
            dishes.append(
                {
                    "name": dish.get("name", "Dish"),
                    "description": dish.get("description", ""),
                    "price": dish.get("price", 0),
                    "image": dish.get("image", "")
                }
            )

    return dishes


def generate_random_reviews(count):
    names = [
        "Олександр", "Софія", "Андрій", "Валерія", "Ігор",
        "Марія", "Дмитро", "Аліна", "Максим", "Катерина"
    ]
    texts = [
        "Неймовірна атмосфера та сервіс.",
        "Страви подані бездоганно, смак на найвищому рівні.",
        "Ідеальне місце для вечері удвох.",
        "Преміум-ресторан, куди хочеться повернутися.",
        "Вишукана кухня та дуже уважний персонал.",
        "Справді дорогий і стильний заклад.",
        "Одна з найкращих італійських кухонь, що пробував.",
        "Естетика, смак і комфорт в одному місці."
    ]

    reviews = []
    for _ in range(count):
        reviews.append(
            {
                "name": random.choice(names),
                "text": random.choice(texts)
            }
        )
    return reviews


@app.route('/pic.png')
def restaurant_image():
    return send_file('pic.png', mimetype='image/png')

@app.route("/register", methods = ['GET','POST'])
def register():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403
        nickname = request.form['nickname']
        email = request.form['email']
        password = request.form['password']

        with Session() as cursor:
            if cursor.query(Users).filter_by(email=email).first() or cursor.query(Users).filter_by(nickname = nickname).first():
                flash('Користувач з таким email або нікнеймом вже існує!', 'danger')
                return render_template('register.html',csrf_token=session["csrf_token"])

            new_user = Users(nickname=nickname, email=email)
            new_user.set_password(password)
            cursor.add(new_user)
            cursor.commit()
            cursor.refresh(new_user)
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template('register.html',csrf_token=session["csrf_token"])

@app.route("/login", methods = ["GET","POST"])
def login():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        password = request.form['password']

        with Session() as cursor:
            user = cursor.query(Users).filter_by(nickname = nickname).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('home'))

            flash('Неправильний nickname або пароль!', 'danger')

    return render_template('login.html', csrf_token=session["csrf_token"])


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)