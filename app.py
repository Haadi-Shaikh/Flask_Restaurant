import json
import os
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "restaurant-order-system-secret")
app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "127.0.0.1")
app.config["MYSQL_PORT"] = int(os.getenv("MYSQL_PORT", 3306))
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", "")
app.config["MYSQL_DATABASE"] = os.getenv("MYSQL_DATABASE", "restaurant_order_system")
app.config["ADMIN_USERNAME"] = os.getenv("ADMIN_USERNAME", "admin")
app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "admin123")
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_db():
    """Create one MySQL connection per request context."""
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=app.config["MYSQL_HOST"],
            port=app.config["MYSQL_PORT"],
            user=app.config["MYSQL_USER"],
            password=app.config["MYSQL_PASSWORD"],
            database=app.config["MYSQL_DATABASE"],
        )
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def fetch_all(query, params=None):
    cursor = get_db().cursor(dictionary=True)
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_one(query, params=None):
    cursor = get_db().cursor(dictionary=True)
    cursor.execute(query, params or ())
    row = cursor.fetchone()
    cursor.close()
    return row


def execute_query(query, params=None):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, params or ())
    db.commit()
    lastrowid = cursor.lastrowid
    cursor.close()
    return lastrowid


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Please upload a valid image file (png, jpg, jpeg, webp, gif).")

    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(save_path)
    return url_for("static", filename=f"uploads/{filename}")


def get_cart():
    return session.setdefault("cart", [])


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_summary():
    cart = get_cart()
    item_count = sum(item["quantity"] for item in cart)
    total = sum(item["price"] * item["quantity"] for item in cart)
    return {"count": item_count, "total": round(total, 2)}


@app.template_filter("inr")
def format_inr(value):
    amount = float(value or 0)
    return f"\u20b9{amount:,.2f}"


@app.context_processor
def inject_globals():
    return {"cart_summary": cart_summary()}


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in to access the admin area.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/")
def home():
    search_query = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "newest")
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    filters = []
    params = []

    if search_query:
        filters.append("LOWER(name) LIKE %s")
        params.append(f"%{search_query.lower()}%")

    if min_price:
        filters.append("price >= %s")
        params.append(min_price)

    if max_price:
        filters.append("price <= %s")
        params.append(max_price)

    order_map = {
        "price_low": "price ASC",
        "price_high": "price DESC",
        "name_az": "name ASC",
        "name_za": "name DESC",
        "newest": "id DESC",
    }
    order_clause = order_map.get(sort_by, "id DESC")
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    try:
        menu_items = fetch_all(
            f"SELECT * FROM menu {where_clause} ORDER BY {order_clause}",
            tuple(params),
        )
    except Error as exc:
        menu_items = []
        flash(f"Database connection error: {exc}", "danger")
    return render_template(
        "home.html",
        menu_items=menu_items,
        filters={
            "q": search_query,
            "sort": sort_by,
            "min_price": min_price,
            "max_price": max_price,
        },
    )


@app.route("/cart")
def cart():
    return render_template("cart.html", cart_items=get_cart())


@app.route("/cart/add/<int:item_id>", methods=["POST"])
def add_to_cart(item_id):
    menu_item = fetch_one("SELECT * FROM menu WHERE id = %s", (item_id,))
    if not menu_item:
        flash("Menu item not found.", "danger")
        return redirect(url_for("home"))

    cart = get_cart()
    for item in cart:
        if item["id"] == item_id:
            item["quantity"] += 1
            save_cart(cart)
            flash(f"{menu_item['name']} quantity updated in your cart.", "success")
            return redirect(request.referrer or url_for("home"))

    cart.append(
        {
            "id": menu_item["id"],
            "name": menu_item["name"],
            "price": float(menu_item["price"]),
            "image_url": menu_item["image_url"],
            "quantity": 1,
        }
    )
    save_cart(cart)
    flash(f"{menu_item['name']} added to your cart.", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
def update_cart(item_id):
    action = request.form.get("action")
    cart = get_cart()

    for item in cart:
        if item["id"] == item_id:
            if action == "increase":
                item["quantity"] += 1
            elif action == "decrease":
                item["quantity"] -= 1

            if item["quantity"] <= 0:
                cart = [cart_item for cart_item in cart if cart_item["id"] != item_id]
            save_cart(cart)
            flash("Cart updated successfully.", "success")
            break

    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
def remove_from_cart(item_id):
    cart = [item for item in get_cart() if item["id"] != item_id]
    save_cart(cart)
    flash("Item removed from your cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = get_cart()
    if not cart:
        flash("Your cart is empty. Add something delicious first.", "warning")
        return redirect(url_for("home"))

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        table_number = request.form.get("table_number", "").strip()

        if not customer_name or not table_number:
            flash("Customer name and table number are required.", "danger")
            return redirect(url_for("checkout"))

        items_payload = [
            {
                "id": item["id"],
                "name": item["name"],
                "price": item["price"],
                "quantity": item["quantity"],
            }
            for item in cart
        ]
        total_price = sum(item["price"] * item["quantity"] for item in cart)
        execute_query(
            """
            INSERT INTO orders (customer_name, table_number, items, total_price, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                customer_name,
                table_number,
                json.dumps(items_payload),
                total_price,
                "Pending",
            ),
        )
        session.pop("cart", None)
        flash("Order placed successfully.", "success")
        return redirect(url_for("order_success", customer_name=customer_name))

    return render_template("checkout.html", cart_items=cart)


@app.route("/order-success")
def order_success():
    customer_name = request.args.get("customer_name", "Guest")
    return render_template("order_success.html", customer_name=customer_name)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if (
            username == app.config["ADMIN_USERNAME"]
            and password == app.config["ADMIN_PASSWORD"]
        ):
            session["admin_logged_in"] = True
            flash("Welcome back, admin.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    try:
        total_orders = fetch_one("SELECT COUNT(*) AS total FROM orders")["total"]
        pending_orders = fetch_one(
            "SELECT COUNT(*) AS total FROM orders WHERE status = 'Pending'"
        )["total"]
        total_menu_items = fetch_one("SELECT COUNT(*) AS total FROM menu")["total"]
        recent_orders = fetch_all("SELECT * FROM orders ORDER BY id DESC LIMIT 5")
    except Error as exc:
        total_orders = 0
        pending_orders = 0
        total_menu_items = 0
        recent_orders = []
        flash(f"Database connection error: {exc}", "danger")

    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        pending_orders=pending_orders,
        total_menu_items=total_menu_items,
        recent_orders=recent_orders,
    )


@app.route("/admin/menu")
@admin_required
def admin_menu():
    try:
        menu_items = fetch_all("SELECT * FROM menu ORDER BY id DESC")
    except Error as exc:
        menu_items = []
        flash(f"Database connection error: {exc}", "danger")
    return render_template("admin_menu.html", menu_items=menu_items)


@app.route("/admin/menu/add", methods=["GET", "POST"])
@admin_required
def add_menu_item():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        image_url = request.form.get("image_url", "").strip()
        image_file = request.files.get("image_file")

        if not name or not price:
            flash("Name and price are required.", "danger")
            return redirect(url_for("add_menu_item"))

        try:
            uploaded_image_url = save_uploaded_image(image_file)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("add_menu_item"))

        execute_query(
            "INSERT INTO menu (name, price, image_url) VALUES (%s, %s, %s)",
            (name, price, uploaded_image_url or image_url or None),
        )
        flash("Menu item added successfully.", "success")
        return redirect(url_for("admin_menu"))

    return render_template(
        "admin_menu_form.html",
        action="Add",
        menu_item={"name": "", "price": "", "image_url": ""},
    )


@app.route("/admin/menu/edit/<int:item_id>", methods=["GET", "POST"])
@admin_required
def edit_menu_item(item_id):
    menu_item = fetch_one("SELECT * FROM menu WHERE id = %s", (item_id,))
    if not menu_item:
        flash("Menu item not found.", "danger")
        return redirect(url_for("admin_menu"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        image_url = request.form.get("image_url", "").strip()
        image_file = request.files.get("image_file")

        if not name or not price:
            flash("Name and price are required.", "danger")
            return redirect(url_for("edit_menu_item", item_id=item_id))

        try:
            uploaded_image_url = save_uploaded_image(image_file)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("edit_menu_item", item_id=item_id))

        execute_query(
            "UPDATE menu SET name = %s, price = %s, image_url = %s WHERE id = %s",
            (
                name,
                price,
                uploaded_image_url or image_url or menu_item["image_url"] or None,
                item_id,
            ),
        )
        flash("Menu item updated successfully.", "success")
        return redirect(url_for("admin_menu"))

    return render_template("admin_menu_form.html", action="Edit", menu_item=menu_item)


@app.route("/admin/menu/delete/<int:item_id>", methods=["POST"])
@admin_required
def delete_menu_item(item_id):
    execute_query("DELETE FROM menu WHERE id = %s", (item_id,))
    flash("Menu item deleted.", "info")
    return redirect(url_for("admin_menu"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    try:
        orders = fetch_all("SELECT * FROM orders ORDER BY id DESC")
    except Error as exc:
        orders = []
        flash(f"Database connection error: {exc}", "danger")

    for order in orders:
        try:
            order["parsed_items"] = json.loads(order["items"])
        except (TypeError, json.JSONDecodeError):
            order["parsed_items"] = []
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    status = request.form.get("status", "Pending")
    if status not in {"Pending", "Completed"}:
        flash("Invalid order status.", "danger")
        return redirect(url_for("admin_orders"))

    execute_query("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))


if __name__ == "__main__":
    app.run(debug=True)
