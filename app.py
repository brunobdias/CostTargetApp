#.env structure
##FLASK_SECRET_KEY=change_this_to_a_random_string

#DB_SERVER=YOUR_SQL_SERVER_NAME_OR_IP
#DB_DATABASE=YOUR_DATABASE_NAME      ; e.g. Pr3_live
#DB_DRIVER=ODBC Driver 17 for SQL Server
#DB_TRUSTED=YES                      ; we’ll use Windows auth initially

# app.py

from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import socket

from dotenv import load_dotenv
load_dotenv()

from db import (
    list_costtargets, insert_costtarget, update_costtarget,
    list_logs, insert_log,
    list_users, get_or_create_user, update_user_record,
    update_last_login, get_user,
    get_departments, update_department,
    detect_department
)

app = Flask(__name__)
app.secret_key = "123456789"

# ============
# JINJA FILTER
# ============

@app.template_filter("fmt")
def fmt(value):
    """Format datetime to YYYY-MM-DD HH:MM:SS"""
    try:
        return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
    except:
        return ""

# ==========================================
# HELPERS
# ==========================================

def client_ip():
    return request.headers.get("X-Forwarded-For") or request.remote_addr or "unknown"

def client_hostname():
    try:
        return socket.getfqdn()
    except:
        return "unknown"


# ==========================================
# DECORATORS
# ==========================================

def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return render_template("error.html", message="Admin access required.")
        return f(*args, **kwargs)
    return wrapper


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()

        if not username:
            flash("Username required.", "danger")
            return redirect(url_for("login"))

        # Auto-create user if missing
        user = get_or_create_user(username, username)

        if user.is_active == 0:
            return render_template("error.html", message="Your account is inactive.")

        # Update login timestamp
        update_last_login(user.username)

        # Write into session
        session["logged_in"] = True
        session["username"] = user.username
        session["displayname"] = user.displayname
        session["role"] = user.role

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ==========================================
# HOME
# ==========================================

@app.route("/")
@require_login
def home():

    prod_filter = request.args.get("prodnum_filter", "").strip()
    cat_filter = request.args.get("buildcat_filter", "").strip()
    dept_filter = request.args.get("dept_filter", "").strip() or "all"
    sort = request.args.get("sort", "prodnum")
    order = request.args.get("order", "asc")

    rows = list_costtargets(
        prodnum_filter=prod_filter or None,
        buildcat_filter=cat_filter or None,
        dept_filter=dept_filter,
        sort=sort,
        order=order
    )

    departments = get_departments()

    return render_template("list.html",
                           rows=rows,
                           departments=departments,
                           prod_filter=prod_filter,
                           cat_filter=cat_filter,
                           dept_filter=dept_filter,
                           sort=sort,
                           order=order)


# ==========================================
# ADD COSTTARGET
# ==========================================

@app.route("/add", methods=["GET", "POST"])
@require_login
def add_costtarget():

    if request.method == "POST":

        prodnum = int(request.form["prodnum"])
        buildcatnum = int(request.form["buildcatnum"])
        target_cost = float(request.form["target_cost"])
        comments = request.form.get("comments", "")
        username = session["username"]

        ip = client_ip()
        host = client_hostname()

        # Which button was pressed?
        action = request.form.get("action")

        dept_from_form = request.form.get("department_id")

        if dept_from_form and dept_from_form.isdigit():
            department_id = int(dept_from_form)
        else:
            department_id = detect_department(prodnum)

        try:
            insert_costtarget(
                prodnum, buildcatnum, target_cost, comments,
                department_id, username
            )

            insert_log(prodnum, buildcatnum, None, target_cost, username, ip, host)

            if action == "add_another":
                flash("Cost Target added!", "success")
                return redirect(url_for("add_costtarget"))

            flash("Cost Target added successfully!", "success")
            return redirect(url_for("home"))

        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("add_costtarget"))

    departments = get_departments()
    dept_ids = [d.department_id for d in departments]

    return render_template("add.html", departments=departments, dept_ids=dept_ids)


# ==========================================
# EDIT COSTTARGET
# ==========================================

@app.route("/edit/<int:record_id>", methods=["GET", "POST"])
@require_login
def edit_costtarget_page(record_id):

    rows = list_costtargets()
    record = next((r for r in rows if r.id == record_id), None)

    if record is None:
        return render_template("error.html", message="Record not found.")

    if request.method == "POST":
        target_cost = float(request.form["target_cost"])
        comments = request.form.get("comments", "")
        dept_id = int(request.form["department_id"])
        username = session["username"]
        ip = client_ip()
        host = client_hostname()

        update_costtarget(record_id, target_cost, comments, dept_id, username)

        insert_log(record.prodnum, record.buildcatnum,
                   record.target_cost, target_cost,
                   username, ip, host)

        return redirect(url_for("home"))

    departments = get_departments()
    dept_ids = [d.department_id for d in departments]

    return render_template("edit.html",
                           record=record,
                           departments=departments,
                           dept_ids=dept_ids)


# ==========================================
# LOGS
# ==========================================

@app.route("/logs")
@require_login
@require_admin
def logs_page():
    logs = list_logs()
    return render_template("logs.html", logs=logs)


# ==========================================
# USERS (ADMIN)
# ==========================================

@app.route("/users")
@require_login
@require_admin
def users_page():
    users = list_users()
    return render_template("users.html", users=users)


@app.route("/users/edit/<username>", methods=["GET", "POST"])
@require_login
@require_admin
def edit_user_page(username):

    user = get_user(username)

    if request.method == "POST":
        displayname = request.form.get("displayname") or username
        role = request.form.get("role", "user")
        is_active = 1 if request.form.get("is_active") == "1" else 0

        update_user_record(username, displayname, role, is_active)

        return redirect(url_for("users_page"))

    return render_template("edit_user.html", user=user)


# ==========================================
# DEPARTMENTS (ADMIN)
# ==========================================

@app.route("/departments")
@require_login
@require_admin
def departments_page():
    departments = get_departments()
    return render_template("departments.html", departments=departments)


@app.route("/departments/edit/<int:dept_id>", methods=["POST"])
@require_login
@require_admin
def edit_department_page(dept_id):

    department_name = request.form.get("department_name", "").strip()
    is_active = 1 if request.form.get("is_active") == "1" else 0

    update_department(dept_id, department_name, is_active)

    return redirect(url_for("departments_page"))


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
