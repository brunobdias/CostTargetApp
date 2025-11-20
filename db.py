import pyodbc
import os

# Load from .env
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_TRUSTED = os.getenv("DB_TRUSTED", "YES")


def get_connection():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
    )
    if DB_TRUSTED.upper() == "YES":
        conn_str += "Trusted_Connection=yes;"
    return pyodbc.connect(conn_str)

def set_session_context(username, hostname, ip):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("EXEC sys.sp_set_session_context 'username', ?", (username,))
    cur.execute("EXEC sys.sp_set_session_context 'hostname', ?", (hostname,))
    cur.execute("EXEC sys.sp_set_session_context 'ip_address', ?", (ip,))
    conn.commit()
    conn.close()

# ==================================================
# USERS
# ==================================================

def get_user(username: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT username, displayname, role, is_active, created_at, last_login_at
        FROM aux_costtarget_user
        WHERE username = ?
    """, (username,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(username: str, displayname: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO aux_costtarget_user (username, displayname, role, is_active)
        VALUES (?, ?, 'user', 1)
    """, (username, displayname))
    conn.commit()
    conn.close()


def get_or_create_user(username: str, displayname: str):
    row = get_user(username)
    if row is None:
        create_user(username, displayname)
        row = get_user(username)
    return row


def update_last_login(username: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE aux_costtarget_user
        SET last_login_at = GETDATE()
        WHERE username = ?
    """, (username,))
    conn.commit()
    conn.close()


def list_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT username, displayname, role, is_active, created_at, last_login_at
        FROM aux_costtarget_user
        ORDER BY username
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_user_record(username: str, displayname: str, role: str, is_active: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE aux_costtarget_user
        SET displayname = ?, role = ?, is_active = ?
        WHERE username = ?
    """, (displayname, role, is_active, username))
    conn.commit()
    conn.close()


# ==================================================
# DEPARTMENTS
# ==================================================

def get_departments():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT department_id, department_name AS department_name, is_active
        FROM aux_department
        ORDER BY department_id
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_department(dept_id: int, department_name: str, is_active: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE aux_department
        SET department_name = ?, is_active = ?
        WHERE department_id = ?
    """, (department_name, is_active, dept_id))
    conn.commit()
    conn.close()


# ==================================================
# COST TARGETS
# ==================================================

def detect_department(prodnum: int):
    first_digit = int(str(prodnum)[0])
    return first_digit


def list_costtargets(prodnum_filter=None, buildcat_filter=None, dept_filter=None,
                     sort="prodnum", order="asc"):

    # VALID SORT MAPPING
    sort_map = {
        "prodnum": "c.prodnum",
        "buildcatnum": "c.buildcatnum",
        "target_cost": "c.target_cost",
        "department": "d.department_name",   # FIX
        "created_at": "c.created_at",
        "updated_at": "c.updated_at"
    }

    # Prevent SQL injection by enforcing allowed sort fields
    sort_column = sort_map.get(sort, "c.prodnum")

    # Order validation
    order = "asc" if order.lower() != "desc" else "desc"

    sql = f"""
        SELECT c.id, c.prodnum, c.buildcatnum, c.target_cost, c.comments,
               c.updated_by, c.updated_at,
               d.department_name AS department_name, c.department_id,
               c.created_at, c.created_by
        FROM aux_costtarget c
        LEFT JOIN aux_department d ON c.department_id = d.department_id
        WHERE 1=1
    """

    params = []

    # PRODUCT FILTER
    if prodnum_filter:
        sql += " AND CAST(c.prodnum AS NVARCHAR) LIKE ?"
        params.append(prodnum_filter.replace("*", "%"))

    # CATEGORY FILTER
    if buildcat_filter:
        sql += " AND CAST(c.buildcatnum AS NVARCHAR) LIKE ?"
        params.append(buildcat_filter.replace("*", "%"))

    # DEPARTMENT FILTER
    if dept_filter and dept_filter != "all":
        sql += " AND c.department_id = ?"
        params.append(int(dept_filter))

    # FINAL ORDER BY
    sql += f" ORDER BY {sort_column} {order}"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_costtarget(prodnum, buildcatnum, target_cost, comments, department_id, username):
    conn = get_connection()
    cur = conn.cursor()

    # Check for duplicate
    cur.execute("""
        SELECT COUNT(*) 
        FROM aux_costtarget 
        WHERE prodnum = ? AND buildcatnum = ?
    """, (prodnum, buildcatnum))
    
    row_count = cur.fetchone()[0]

    if row_count > 0:
        raise ValueError("A Cost Target for this Product + Category already exists.")

    # Normal insert…
    cur.execute("""
        INSERT INTO aux_costtarget
            (prodnum, buildcatnum, target_cost, comments,
             department_id, created_by, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (prodnum, buildcatnum, target_cost, comments,
          department_id, username, username))

    conn.commit()
    conn.close()

def update_costtarget(record_id: int, target_cost: float, comments: str,
                      department_id: int, username: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE aux_costtarget
        SET target_cost = ?, comments = ?, department_id = ?,
            updated_by = ?, updated_at = GETDATE()
        WHERE id = ?
    """, (target_cost, comments, department_id, username, record_id))

    conn.commit()
    conn.close()


# ==================================================
# LOGS
# ==================================================

def list_logs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT log_id, prodnum, buildcatnum, old_value, new_value,
               changed_by, changed_at, source, comment,
               hostname, ip_address
        FROM aux_costtarget_log
        ORDER BY changed_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_log(prodnum, buildcatnum, old_value, new_value, username, ip, host):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO aux_costtarget_log
        (prodnum, buildcatnum, old_value, new_value,
         changed_by, changed_at, source, comment, hostname, ip_address)
        VALUES (?, ?, ?, ?, ?, GETDATE(), 'web', NULL, ?, ?)
    """, (prodnum, buildcatnum, old_value, new_value,
          username, host, ip))
    conn.commit()
    conn.close()
