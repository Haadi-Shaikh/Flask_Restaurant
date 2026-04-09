# Royal Restaurant

A modern Flask + MySQL restaurant ordering web app with a polished Bootstrap 5 interface for customers and admins.

## Folder Structure

```text
restaurant-order-system/
|-- app.py
|-- requirements.txt
|-- schema.sql
|-- README.md
|-- static/
|   |-- css/
|   |   `-- style.css
|   `-- js/
|       `-- app.js
|   `-- uploads/
|       `-- .gitkeep
`-- templates/
    |-- base.html
    |-- home.html
    |-- cart.html
    |-- checkout.html
    |-- order_success.html
    |-- admin_login.html
    |-- admin_dashboard.html
    |-- admin_menu.html
    |-- admin_menu_form.html
    `-- admin_orders.html
```

## Features

- Customer menu browsing with stylish cards
- Search, price filtering, and menu sorting
- Session-based shopping cart
- Checkout with customer name and table number
- Order confirmation page
- Admin login and dashboard
- Menu management: add, edit, delete, and image upload
- Orders table with status updates
- Flash alerts and responsive Bootstrap 5 UI

## MySQL Setup (XAMPP)

1. Start `Apache` and `MySQL` from XAMPP Control Panel.
2. Open `phpMyAdmin` or MySQL CLI.
3. Run the SQL from `schema.sql`.
   This seeds the database with sample Indian dishes as well.

## Project Setup

1. Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Optional: set environment variables if your MySQL settings differ from defaults:

```powershell
$env:SECRET_KEY="change-me"
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD=""
$env:MYSQL_DATABASE="restaurant_order_system"
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="admin123"
```

4. Run the Flask app:

```powershell
python app.py
```

5. Open `http://127.0.0.1:5000`

## Default Admin Login

- Username: `admin`
- Password: `admin123`

## Notes

- Cart data is stored in Flask session.
- Orders store item payload in a JSON column.
- Menu images can be local URLs or remote URLs.
- Admin can upload image files, which are stored in `static/uploads`.
- If MySQL connection fails, the home page shows a flash error to help diagnose setup issues.
