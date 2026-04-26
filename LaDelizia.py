import json
import os
import random
import secrets

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import LoginManager, login_required, login_user, logout_user

from LaDelizia_db import Session, Users

app = Flask(__name__)

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
    with Session() as db_session:
        return db_session.query(Users).filter_by(id=user_id).first()


def ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def is_valid_csrf():
    return request.form.get("csrf_token") == session.get("csrf_token")


def send_project_image(filename):
    image_path = os.path.join(app.root_path, filename)
    return send_file(image_path, mimetype="image/png")

@app.after_request
def apply_csp(response):
    nonce = secrets.token_urlsafe(16)
    csp = (
        f"default-src 'self'; "
        f"img-src 'self' https: data:; "
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
    ensure_csrf_token()

    dishes = load_dishes_from_json()
    reviews = generate_random_reviews(6)

    return render_template(
        'home.html',
        dishes=dishes,
        reviews=reviews
    )


@app.route('/menu')
def menu_page():
    ensure_csrf_token()
    menu_categories = load_menu_categories_from_json()
    return render_template('menu.html', menu_categories=menu_categories)


def normalize_category_name(raw_name):
    return raw_name.replace("_", " ").title()


def load_menu_categories_from_json():
    with open('menu.json', 'r', encoding='utf-8') as file:
        menu_data = json.load(file)

    categories = menu_data.get('menu', {})
    menu_categories = []

    for category_name, category_items in categories.items():
        normalized_name = normalize_category_name(category_name)
        dishes = []

        for dish in category_items:
            dishes.append(
                {
                    "name": dish.get("name", "Dish"),
                    "description": dish.get("description", ""),
                    "price": dish.get("price", 0),
                    "image": dish.get("image", ""),
                }
            )

        menu_categories.append(
            {
                "key": category_name,
                "title": normalized_name,
                "dishes": dishes,
            }
        )

    return menu_categories


def load_dishes_from_json():
    dishes = []
    for category in load_menu_categories_from_json():
        dishes.extend(category["dishes"])

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
    return send_project_image("pic.png")

@app.route('/collective.png')
def collective_image():
    return send_project_image("collective.png")

@app.route("/register", methods = ['GET','POST'])
def register():
    ensure_csrf_token()

    if request.method == 'POST':
        if not is_valid_csrf():
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        email = request.form['email']
        password = request.form['password']

        with Session() as db_session:
            email_exists = db_session.query(Users).filter_by(email=email).first()
            nickname_exists = db_session.query(Users).filter_by(nickname=nickname).first()

            if email_exists or nickname_exists:
                flash('Користувач з таким email або нікнеймом вже існує!', 'danger')
                return render_template('register.html', csrf_token=session["csrf_token"])

            new_user = Users(nickname=nickname, email=email)
            new_user.set_password(password)
            db_session.add(new_user)
            db_session.commit()
            db_session.refresh(new_user)
            login_user(new_user)
            return redirect(url_for('home'))

    return render_template('register.html', csrf_token=session["csrf_token"])

@app.route("/login", methods = ["GET","POST"])
def login():
    ensure_csrf_token()

    if request.method == 'POST':
        if not is_valid_csrf():
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        password = request.form['password']

        with Session() as db_session:
            user = db_session.query(Users).filter_by(nickname=nickname).first()
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