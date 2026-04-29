import json
import os
import random
import secrets
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from LaDelizia_db import Session, Users

app = Flask(__name__)
CARTS_DIR = Path(app.root_path) / "carts"
ORDERS_DIR = Path(app.root_path) / "orders"
BOOKING_DIR = Path(app.root_path) / "bookings"
TABLES_STATE_FILE = BOOKING_DIR / "tables.json"
TABLE_COUNT = 12
TIME_SLOTS = ["17:00", "18:00", "19:00", "20:00", "21:00"]

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
    return render_template(
        "menu.html",
        menu_categories=menu_categories,
        csrf_token=session["csrf_token"],
        page_title="Меню LaDelizia",
        back_url=url_for("home"),
        checkout_endpoint=url_for("checkout"),
    )


@app.route('/booking/tables')
@login_required
def booking_tables_page():
    ensure_csrf_token()
    table_ids = list(range(1, TABLE_COUNT + 1))
    selected_time = session.get("selected_time", TIME_SLOTS[0])
    reserved_by_slot = load_reserved_tables()
    return render_template(
        "booking_tables.html",
        csrf_token=session["csrf_token"],
        table_ids=table_ids,
        reserved_tables=reserved_by_slot.get(selected_time, []),
        reserved_by_slot=reserved_by_slot,
        selected_table=session.get("selected_table"),
        selected_time=selected_time,
        time_slots=TIME_SLOTS,
    )


@app.route('/booking/menu')
@login_required
def booking_menu_page():
    ensure_csrf_token()
    selected_table = session.get("selected_table")
    selected_time = session.get("selected_time")
    if not selected_table or not selected_time:
        return redirect(url_for("booking_tables_page"))

    menu_categories = load_menu_categories_from_json()
    return render_template(
        "menu.html",
        menu_categories=menu_categories,
        csrf_token=session["csrf_token"],
        page_title=f"Замовлення: стіл №{selected_table} на {selected_time}",
        back_url=url_for("booking_tables_page"),
        checkout_endpoint=url_for("booking_checkout"),
    )


def _cart_path_for_user(user_id):
    CARTS_DIR.mkdir(parents=True, exist_ok=True)
    return CARTS_DIR / f"user_{user_id}.json"


def load_user_cart(user_id):
    path = _cart_path_for_user(user_id)
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as cart_file:
            data = json.load(cart_file)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_user_cart(user_id, items):
    path = _cart_path_for_user(user_id)
    with open(path, "w", encoding="utf-8") as cart_file:
        json.dump(items, cart_file, ensure_ascii=False, indent=2)


def append_user_order(user_id, items, metadata=None):
    ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    order_file = ORDERS_DIR / f"user_{user_id}.jsonl"
    order_payload = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "items": items,
    }
    if isinstance(metadata, dict) and metadata:
        order_payload["metadata"] = metadata
    with open(order_file, "a", encoding="utf-8") as target:
        target.write(json.dumps(order_payload, ensure_ascii=False) + "\n")


def load_reserved_tables():
    BOOKING_DIR.mkdir(parents=True, exist_ok=True)
    if not TABLES_STATE_FILE.exists():
        return {}

    try:
        with open(TABLES_STATE_FILE, "r", encoding="utf-8") as table_file:
            data = json.load(table_file)
            if isinstance(data, list):
                # backward compatibility: old format without time slots
                return {TIME_SLOTS[0]: [int(table) for table in data if isinstance(table, int) or str(table).isdigit()]}
            if not isinstance(data, dict):
                return {}

            normalized = {}
            for slot, table_ids in data.items():
                if slot not in TIME_SLOTS or not isinstance(table_ids, list):
                    continue
                normalized[slot] = [int(table) for table in table_ids if isinstance(table, int) or str(table).isdigit()]
            return normalized
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def save_reserved_tables(tables_by_slot):
    BOOKING_DIR.mkdir(parents=True, exist_ok=True)
    normalized = {}
    for slot in TIME_SLOTS:
        raw_ids = tables_by_slot.get(slot, []) if isinstance(tables_by_slot, dict) else []
        normalized[slot] = sorted(set(int(table_id) for table_id in raw_ids if isinstance(table_id, int) or str(table_id).isdigit()))
    with open(TABLES_STATE_FILE, "w", encoding="utf-8") as table_file:
        json.dump(normalized, table_file, ensure_ascii=False, indent=2)


def normalize_cart_items(raw_items):
    if not isinstance(raw_items, list):
        return []

    normalized = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        if not name:
            continue

        try:
            qty = int(item.get("qty", 1))
        except (TypeError, ValueError):
            qty = 1
        if qty < 1:
            qty = 1

        try:
            price = float(item.get("price", 0))
        except (TypeError, ValueError):
            price = 0

        normalized.append(
            {
                "name": name,
                "description": str(item.get("description", "")).strip(),
                "image": str(item.get("image", "")).strip(),
                "price": price,
                "qty": qty,
            }
        )

    return normalized


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


@app.route("/api/cart", methods=["GET"])
@login_required
def get_user_cart():
    return jsonify({"items": load_user_cart(current_user.id)})


@app.route("/api/cart", methods=["POST"])
@login_required
def update_user_cart():
    header_csrf = request.headers.get("X-CSRF-Token")
    if header_csrf != session.get("csrf_token"):
        return jsonify({"error": "Запит заблоковано!"}), 403

    payload = request.get_json(silent=True) or {}
    items = normalize_cart_items(payload.get("items", []))
    save_user_cart(current_user.id, items)
    return jsonify({"success": True, "items": items})


@app.route("/api/checkout", methods=["POST"])
@login_required
def checkout():
    header_csrf = request.headers.get("X-CSRF-Token")
    if header_csrf != session.get("csrf_token"):
        return jsonify({"error": "Запит заблоковано!"}), 403

    payload = request.get_json(silent=True) or {}
    items = normalize_cart_items(payload.get("items", []))
    if not items:
        return jsonify({"error": "Кошик порожній"}), 400

    append_user_order(current_user.id, items)
    save_user_cart(current_user.id, [])
    return jsonify({"success": True})


@app.route("/api/booking/select-table", methods=["POST"])
@login_required
def select_booking_table():
    header_csrf = request.headers.get("X-CSRF-Token")
    if header_csrf != session.get("csrf_token"):
        return jsonify({"error": "Запит заблоковано!"}), 403

    payload = request.get_json(silent=True) or {}
    try:
        table_id = int(payload.get("table_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Невірний столик"}), 400
    time_slot = str(payload.get("time_slot", "")).strip()
    if time_slot not in TIME_SLOTS:
        return jsonify({"error": "Невірний час бронювання"}), 400

    if table_id < 1 or table_id > TABLE_COUNT:
        return jsonify({"error": "Невірний номер столика"}), 400

    tables_by_slot = load_reserved_tables()
    reserved_tables = tables_by_slot.get(time_slot, [])
    current_selected = session.get("selected_table")
    current_selected_time = session.get("selected_time")
    if table_id in reserved_tables and not (current_selected == table_id and current_selected_time == time_slot):
        return jsonify({"error": "Цей столик вже зайнятий"}), 409

    if current_selected == table_id and current_selected_time == time_slot:
        return jsonify({"success": True, "redirect_url": url_for("booking_menu_page")})

    if table_id not in reserved_tables:
        reserved_tables.append(table_id)
        tables_by_slot[time_slot] = reserved_tables
        save_reserved_tables(tables_by_slot)
    session["selected_table"] = table_id
    session["selected_time"] = time_slot
    return jsonify({"success": True, "redirect_url": url_for("booking_menu_page")})


@app.route("/api/booking/checkout", methods=["POST"])
@login_required
def booking_checkout():
    header_csrf = request.headers.get("X-CSRF-Token")
    if header_csrf != session.get("csrf_token"):
        return jsonify({"error": "Запит заблоковано!"}), 403

    selected_table = session.get("selected_table")
    selected_time = session.get("selected_time")
    if not selected_table or not selected_time:
        return jsonify({"error": "Спочатку оберіть столик"}), 400

    payload = request.get_json(silent=True) or {}
    items = normalize_cart_items(payload.get("items", []))
    if not items:
        return jsonify({"error": "Кошик порожній"}), 400

    append_user_order(
        current_user.id,
        items,
        metadata={"table_id": selected_table, "time_slot": selected_time},
    )
    save_user_cart(current_user.id, [])
    session.pop("selected_table", None)
    session.pop("selected_time", None)
    return jsonify({"success": True, "redirect_url": url_for("home")})


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