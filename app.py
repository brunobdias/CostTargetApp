#.env structure
##FLASK_SECRET_KEY=change_this_to_a_random_string

#DB_SERVER=YOUR_SQL_SERVER_NAME_OR_IP
#DB_DATABASE=YOUR_DATABASE_NAME      ; e.g. Pr3_live
#DB_DRIVER=ODBC Driver 17 for SQL Server
#DB_TRUSTED=YES                      ; we’ll use Windows auth initially

# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
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

@app.template_filter("fmt")
def fmt(value):
    if value:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return ""

def get_remote_user_raw():
    """
    Get the Windows username forwarded by IIS/ARR.
    IIS sets HTTP_REMOTE_USER → REMOTE_USER header.
    """
    return (
        request.headers.get("REMOTE_USER")
        or request.environ.get("REMOTE_USER")
        or request.environ.get("HTTP_REMOTE_USER")
    )


def normalize_windows_username(remote_user: str) -> str:
    """Convert DOMAIN\\user or user@domain into 'user'."""
    if not remote_user:
        return None
    if "\\" in remote_user:
        remote_user = remote_user.split("\\", 1)[1]
    if "@" in remote_user:
        remote_user = remote_user.split("@", 1)[0]
    return remote_user.lower()

# ==================================================
# DECORATORS
# ==================================================

# ==================================================
# AUTO-LOGIN FROM WINDOWS AUTHENTICATION
# ==================================================

@app.before_request
def auto_login_from_windows():
    # Ignore static
    if request.endpoint in ("static",):
        return

    raw_remote = get_remote_user_raw()

    if not raw_remote:
        # Do nothing; require_login() will catch it
        return

    username = normalize_windows_username(raw_remote)

    # If session already correct, skip DB operations
    if session.get("logged_in") and session.get("username") == username:
        return

    # Use your existing helper
    user_row = get_or_create_user(username, username)

    if not user_row.is_active:
        return render_template(
            "error.html",
            message="Your account is inactive.",
        ), 403

    # Update timestamp
    update_last_login(user_row.username)

    # Store in session
    session["logged_in"] = True
    session["username"] = user_row.username
    session["displayname"] = user_row.displayname
    session["role"] = user_row.role

def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return (
                "Unauthorized: No Windows authentication detected. "
                "Check IIS + Intranet settings.",
                401,
            )
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return render_template("error.html",
                                   message="Admin access required.")
        return f(*args, **kwargs)
    return wrapper


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    raw_remote = get_remote_user_raw()

    if raw_remote:
        return redirect("/")

    return (
        "Windows authentication failed (REMOTE_USER missing). "
        "Ensure browser is in Local Intranet zone.",
        401,
    )

@app.route("/logout")
def logout():
    session.clear()
    return (
        "Session cleared. Browser will re-login automatically via Windows SSO.",
        200,
    )


# ==================================================
# HOME (LIST)
# ==================================================

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


# ==================================================
# ADD COSTTARGET
# ==================================================

@app.route("/add", methods=["GET", "POST"])
@require_login
def add_costtarget():
    if request.method == "POST":

        prodnum = int(request.form["prodnum"])
        buildcatnum = int(request.form["buildcatnum"])
        target_cost = float(request.form["target_cost"])
        comments = request.form.get("comments", "")
        username = session["username"]
        
        # Which button was pressed?
        action = request.form.get("action")   # save or add_another

        # Get user selection (may be empty)
        dept_from_form = request.form.get("department_id")

        if dept_from_form and dept_from_form.isdigit():
            department_id = int(dept_from_form)
        else:
            department_id = detect_department(prodnum)

        try:
            insert_costtarget(
                prodnum=prodnum,
                buildcatnum=buildcatnum,
                target_cost=target_cost,
                comments=comments,
                department_id=department_id,
                username=username,
            )
            
            insert_log(prodnum, buildcatnum, None, target_cost, username)
            
            if action == "add_another":
                flash("Cost Target added! You can add another", "success")    
                return redirect(url_for("add_costtarget"))
            
            flash("Cost Target added successfully!", "success")
            return redirect(url_for("home"))
            
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("add_costtarget"))
        
    # GET request
    departments = get_departments()
    dept_ids = [d.department_id for d in departments]

    return render_template(
        "add.html",
        departments=departments,
        dept_ids=dept_ids
    )


# ==================================================
# EDIT COSTTARGET
# ==================================================

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

        update_costtarget(record_id, target_cost, comments,
                          dept_id, username)

        return redirect(url_for("home"))

    departments = get_departments()
    dept_ids = [d.department_id for d in departments]

    return render_template("edit.html",
                           record=record,
                           departments=departments,
                           dept_ids=dept_ids)
    
# ==================================================
# LOGS
# ==================================================

@app.route("/logs")
@require_login
@require_admin
def logs_page():
    logs = list_logs()
    return render_template("logs.html", logs=logs)


# ==================================================
# USERS (ADMIN)
# ==================================================

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


# ==================================================
# DEPARTMENTS (ADMIN)
# ==================================================

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


# ==================================================
# START
# ==================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
