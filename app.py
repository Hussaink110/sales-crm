from flask import Flask, render_template, request, redirect, session
from database import init_db, get_db

app = Flask(__name__)
app.secret_key = "supersecret"
APP_VERSION = "v1.0"
init_db()

# ---------------------------
# Public Enquiry Form
# ---------------------------
@app.route("/", methods=["GET", "POST"])
def enquiry():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        service = request.form.get("service")
        message = request.form["message"]

        conn = get_db()
        conn.execute(
            "INSERT INTO enquiries (name, phone, email, message, status) VALUES (?, ?, ?, ?, 'New')",
            (name, phone, email, message),
        )


        return redirect("/thank-you")

    return render_template("enquiry.html")


@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html")

# ---------------------------
# Admin Login
# ---------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=? AND role='admin'",
            (email, password),
        ).fetchone()
        conn.close()

        if user:
            session["admin"] = user["id"]
            return redirect("/admin/dashboard")

    return render_template("admin_login.html", version=APP_VERSION)

# ---------------------------
# Admin Dashboard
# ---------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin/login")

    conn = get_db()
    enquiries = conn.execute("SELECT * FROM enquiries ORDER BY created_at DESC").fetchall()
    conn.close()

    return render_template("admin_dashboard.html", enquiries=enquiries, version=APP_VERSION)


@app.route("/admin/assign/<int:enquiry_id>", methods=["GET", "POST"])
def assign_enquiry(enquiry_id):
    if "admin" not in session:
        return redirect("/admin/login")

    conn = get_db()

    sales_users = conn.execute(
        "SELECT * FROM users WHERE role='sales'"
    ).fetchall()

    if request.method == "POST":
        sales_id = request.form.get("sales_id")

        if sales_id:
            conn.execute(
                "UPDATE enquiries SET assigned_to=?, status='Assigned' WHERE id=?",
                (sales_id, enquiry_id),
            )
            conn.commit()
            conn.close()
            return redirect("/admin/dashboard")

    enquiry = conn.execute(
        "SELECT * FROM enquiries WHERE id=?", (enquiry_id,)
    ).fetchone()

    conn.close()
    return render_template(
        "assign.html", enquiry=enquiry, sales_users=sales_users
    )


@app.route("/sales/login", methods=["GET", "POST"])
def sales_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=? AND role='sales'",
            (email, password),
        ).fetchone()
        conn.close()

        if user:
            session["sales"] = user["id"]
            return redirect("/sales/dashboard")

    return render_template("sales_login.html", version=APP_VERSION)

@app.route("/sales/dashboard")
def sales_dashboard():
    if "sales" not in session:
        return redirect("/sales/login")

    sales_id = session["sales"]

    conn = get_db()
    enquiries = conn.execute(
        "SELECT * FROM enquiries WHERE assigned_to=?",
        (sales_id,),
    ).fetchall()
    conn.close()

    return render_template("sales_dashboard.html", enquiries=enquiries,version=APP_VERSION)

@app.route("/sales/update/<int:enquiry_id>", methods=["GET", "POST"])
def update_status(enquiry_id):
    if "sales" not in session:
        return redirect("/sales/login")

    conn = get_db()

    if request.method == "POST":
        status = request.form["status"]

        conn.execute(
            "UPDATE enquiries SET status=? WHERE id=?",
            (status, enquiry_id),
        )
        conn.commit()
        conn.close()
        return redirect("/sales/dashboard")

    enquiry = conn.execute(
        "SELECT * FROM enquiries WHERE id=?", (enquiry_id,)
    ).fetchone()

    conn.close()
    return render_template("update_status.html", enquiry=enquiry, version=APP_VERSION)


@app.route("/admin/add-sales", methods=["GET", "POST"])
def add_sales():
    if "admin" not in session:
        return redirect("/admin/login")

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'sales')",
            (name, email, password),
        )
        conn.commit()
        conn.close()

        return redirect("/admin/dashboard")

    return render_template("add_sales.html", version=APP_VERSION)

@app.route("/sales/view/<int:enquiry_id>")
def sales_view(enquiry_id):
    if "sales" not in session:
        return redirect("/sales/login")

    sales_id = session["sales"]

    conn = get_db()

    # Ensure sales can only view their assigned enquiries
    enquiry = conn.execute(
        "SELECT * FROM enquiries WHERE id=? AND assigned_to=?",
        (enquiry_id, sales_id),
    ).fetchone()

    conn.close()

    if not enquiry:
        return "Unauthorized access", 403

    return render_template("sales_view.html", enquiry=enquiry, version=APP_VERSION)



if __name__ == "__main__":
    app.run()

# Required for Render
app = app
