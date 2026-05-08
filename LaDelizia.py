import json
import os
import random
import secrets
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from LaDelizia_db import Session, Users

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # If python-dotenv is not installed, standard environment variables still work.
    pass

app = Flask(__name__)
CARTS_DIR = Path(app.root_path) / "carts"
ORDERS_DIR = Path(app.root_path) / "orders"
BOOKING_DIR = Path(app.root_path) / "bookings"
TABLES_STATE_FILE = BOOKING_DIR / "tables.json"
LOCAL_USERS_FILE = Path(app.root_path) / "local_users.json"
TABLE_COUNT = 12
TIME_SLOTS = ["17:00", "18:00", "19:00", "20:00", "21:00"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['MAX_FORM_MEMORY_SIZE'] = 1024 * 1024  # 1MB
app.config['MAX_FORM_PARTS'] = 500

app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

app.config['SECRET_KEY'] = '#cv)3v7w$*s3fk;5c!@y0?:?№3"9)#'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class LocalAuthUser(UserMixin):
    def __init__(self, nickname, email="", password_hash=""):
        self.nickname = nickname
        self.email = email
        self.password_hash = password_hash

    @property
    def id(self):
        return f"local_{self.nickname}"

    def get_id(self):
        return self.id


def load_local_users():
    if not LOCAL_USERS_FILE.exists():
        return {}
    try:
        with open(LOCAL_USERS_FILE, "r", encoding="utf-8") as local_users_file:
            users = json.load(local_users_file)
            return users if isinstance(users, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_local_users(users_map):
    with open(LOCAL_USERS_FILE, "w", encoding="utf-8") as local_users_file:
        json.dump(users_map, local_users_file, ensure_ascii=False, indent=2)


def find_local_user_by_nickname(nickname):
    users = load_local_users()
    payload = users.get(nickname)
    if not isinstance(payload, dict):
        return None
    return LocalAuthUser(
        nickname=nickname,
        email=str(payload.get("email", "")),
        password_hash=str(payload.get("password_hash", "")),
    )


def create_local_user(nickname, email, password):
    users = load_local_users()
    if nickname in users:
        return None, "Користувач з таким нікнеймом вже існує!"
    if any(str(data.get("email", "")).lower() == email.lower() for data in users.values() if isinstance(data, dict)):
        return None, "Користувач з таким email вже існує!"

    users[nickname] = {
        "email": email,
        "password_hash": generate_password_hash(password),
    }
    save_local_users(users)
    return find_local_user_by_nickname(nickname), None


@login_manager.user_loader
def load_user(user_id):
    if user_id and str(user_id).startswith("local_"):
        nickname = str(user_id).replace("local_", "", 1)
        return find_local_user_by_nickname(nickname)
    try:
        with Session() as db_session:
            return db_session.query(Users).filter_by(id=user_id).first()
    except Exception:
        return None


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


@app.route('/careers')
def careers_page():
    ensure_csrf_token()
    return render_template("careers_unavailable.html", csrf_token=session["csrf_token"])


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
        require_auth_checkout=True,
        enable_cart=False,
    )


@app.route('/booking/tables')
def booking_tables_page():
    ensure_csrf_token()
    table_ids = list(range(1, TABLE_COUNT + 1))
    selected_time = session.get("selected_time", TIME_SLOTS[0])
    if selected_time not in TIME_SLOTS:
        selected_time = TIME_SLOTS[0]
        session["selected_time"] = selected_time
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
        require_auth_checkout=False,
        enable_cart=True,
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


def get_order_owner_id():
    if current_user.is_authenticated:
        return str(current_user.id)

    guest_order_id = session.get("guest_order_id")
    if not guest_order_id:
        guest_order_id = f"guest_{secrets.token_hex(8)}"
        session["guest_order_id"] = guest_order_id
    return guest_order_id


def save_last_order_to_session(items, metadata=None):
    session["last_order"] = {
        "items": items,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def load_reserved_tables():
    BOOKING_DIR.mkdir(parents=True, exist_ok=True)
    if not TABLES_STATE_FILE.exists():
        empty_tables = {slot: [] for slot in TIME_SLOTS}
        save_reserved_tables(empty_tables)
        return empty_tables

    try:
        with open(TABLES_STATE_FILE, "r", encoding="utf-8") as table_file:
            data = json.load(table_file)
            if isinstance(data, list):
                # backward compatibility: old format without time slots
                fallback_tables = {slot: [] for slot in TIME_SLOTS}
                fallback_tables[TIME_SLOTS[0]] = [int(table) for table in data if isinstance(table, int) or str(table).isdigit()]
                save_reserved_tables(fallback_tables)
                return fallback_tables
            if not isinstance(data, dict):
                empty_tables = {slot: [] for slot in TIME_SLOTS}
                save_reserved_tables(empty_tables)
                return empty_tables

            normalized = {}
            for slot, table_ids in data.items():
                if slot not in TIME_SLOTS or not isinstance(table_ids, list):
                    continue
                normalized[slot] = [int(table) for table in table_ids if isinstance(table, int) or str(table).isdigit()]
            if not normalized:
                empty_tables = {slot: [] for slot in TIME_SLOTS}
                save_reserved_tables(empty_tables)
                return empty_tables
            merged_tables = {slot: normalized.get(slot, []) for slot in TIME_SLOTS}
            return merged_tables
    except (json.JSONDecodeError, OSError, ValueError):
        empty_tables = {slot: [] for slot in TIME_SLOTS}
        save_reserved_tables(empty_tables)
        return empty_tables


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


def _normalize_text(text):
    return " ".join(str(text).lower().strip().split())


def build_restaurant_context():
    menu_categories = load_menu_categories_from_json()
    menu_lines = []
    for category in menu_categories:
        category_title = str(category.get("title", "")).strip()
        dish_lines = []
        for dish in category.get("dishes", []):
            dish_name = str(dish.get("name", "")).strip()
            dish_price = dish.get("price", 0)
            dish_description = str(dish.get("description", "")).strip()
            if dish_name:
                dish_lines.append(f"- {dish_name} ({dish_price} грн): {dish_description}")
        if dish_lines:
            menu_lines.append(f"{category_title}:\n" + "\n".join(dish_lines))

    return (
        "Ти AI-помічник ресторану LaDelizia. Відповідай коротко, привітно, українською.\n"
        "Що ти знаєш про ресторан:\n"
        "- Назва: LaDelizia\n"
        "- Адреса: Івано-Франківськ, вул. Незалежності, 31\n"
        f"- Часи бронювання: {', '.join(TIME_SLOTS)}\n"
        "- Можна бронювати столик через сайт.\n\n"
        "Меню:\n"
        + "\n\n".join(menu_lines)
    )


def ask_openai_about_restaurant(user_message):
    if not OPENAI_API_KEY:
        return None

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": build_restaurant_context()},
            {"role": "user", "content": str(user_message)},
        ],
        "temperature": 0.4,
        "max_tokens": 220,
    }

    request_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=request_data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            choices = response_data.get("choices", [])
            if not choices:
                return None
            message = choices[0].get("message", {})
            content = str(message.get("content", "")).strip()
            return content or None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def build_assistant_reply(raw_message):
    message = _normalize_text(raw_message)
    if not message:
        return "Напишіть ваше питання: про страви, меню, бронювання або ресторан."

    ai_reply = ask_openai_about_restaurant(raw_message)
    if ai_reply:
        return ai_reply

    menu_categories = load_menu_categories_from_json()
    dishes = []
    for category in menu_categories:
        for dish in category.get("dishes", []):
            dishes.append(
                {
                    "name": str(dish.get("name", "")),
                    "description": str(dish.get("description", "")),
                    "price": dish.get("price", 0),
                    "category": str(category.get("title", "")),
                }
            )

    matched_dish = None
    for dish in dishes:
        dish_name = _normalize_text(dish["name"])
        if dish_name and dish_name in message:
            matched_dish = dish
            break

    if any(word in message for word in ["привіт", "добр", "hello", "hi"]):
        return "Вітаю в LaDelizia! Я допоможу з меню, бронюванням столиків, цінами та інформацією про ресторан."

    if matched_dish:
        return (
            f"{matched_dish['name']} ({matched_dish['category']}): "
            f"{matched_dish['description']}. Ціна: {matched_dish['price']} грн."
        )

    if any(word in message for word in ["меню", "категор", "що є", "страв"]):
        category_titles = [category.get("title", "") for category in menu_categories]
        return "У нас є такі категорії меню: " + ", ".join(category_titles) + ". Можу підказати конкретну страву і ціну."

    if any(word in message for word in ["адрес", "де ви", "локац", "знаходитесь"]):
        return "Ми знаходимося в Івано-Франківську, вул. Незалежності, 31."

    if any(word in message for word in ["брон", "столик", "резерв"]):
        return "Для бронювання відкрийте розділ 'БРОНЮВАННЯ', оберіть час і столик. Після цього можна одразу вибрати страви."

    if any(word in message for word in ["час", "графік", "коли ви", "роботи"]):
        return "Бронювання доступні на вечірні слоти: " + ", ".join(TIME_SLOTS) + "."

    if any(word in message for word in ["контакт", "телефон", "дзвін"]):
        return "Наразі на сайті немає окремого номера телефону. Можете написати нам через форму/чат або завітати до ресторану."

    return "Я можу допомогти з меню, цінами, описами страв, бронюванням та інформацією про ресторан. Уточніть питання, будь ласка."


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


@app.route("/api/assistant/chat", methods=["POST"])
def assistant_chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Порожнє повідомлення"}), 400

    reply = build_assistant_reply(message)
    return jsonify({"reply": reply})


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
    save_last_order_to_session(items)
    save_user_cart(current_user.id, [])
    return jsonify({"success": True, "redirect_url": url_for("order_success_page")})


@app.route("/api/booking/select-table", methods=["POST"])
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
        get_order_owner_id(),
        items,
        metadata={"table_id": selected_table, "time_slot": selected_time},
    )
    save_last_order_to_session(items, metadata={"table_id": selected_table, "time_slot": selected_time})
    if current_user.is_authenticated:
        save_user_cart(current_user.id, [])
    session.pop("selected_table", None)
    session.pop("selected_time", None)
    return jsonify({"success": True, "redirect_url": url_for("order_success_page")})


@app.route("/order/success")
def order_success_page():
    ensure_csrf_token()
    last_order = session.get("last_order")
    if not isinstance(last_order, dict) or not isinstance(last_order.get("items"), list):
        flash("Ще немає оформленого замовлення.", "warning")
        return redirect(url_for("home"))
    return render_template("order_success.html", order=last_order, csrf_token=session["csrf_token"])


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

        try:
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
        except Exception:
            local_user, error_text = create_local_user(nickname, email, password)
            if error_text:
                flash(error_text, "danger")
                return render_template('register.html', csrf_token=session["csrf_token"])
            login_user(local_user)
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

        user = None
        try:
            with Session() as db_session:
                user = db_session.query(Users).filter_by(nickname=nickname).first()
                if user and user.check_password(password):
                    login_user(user)
                    return redirect(url_for('home'))
        except Exception:
            user = None

        local_user = find_local_user_by_nickname(nickname)
        if local_user and check_password_hash(local_user.password_hash, password):
            login_user(local_user)
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