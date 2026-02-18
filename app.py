from flask import Flask, render_template, request, redirect, session
from database import init_db, get_db
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import os

app = Flask(__name__)
app.secret_key = "supersecret"
APP_VERSION = "v1.0"
init_db()

def is_admin_user():
    # True admin session
    if "admin" in session:
        return True

    # Sales with admin privilege
    if "sales" in session:
        conn = get_db()
        user = conn.execute(
            "SELECT is_admin FROM users WHERE id=?",
            (session["sales"],),
        ).fetchone()
        conn.close()
        return user and user["is_admin"] == 1

    return False

def migrate_db():
    conn = get_db()
    cursor = conn.cursor()

    columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)")]

    if "can_view" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN can_view INTEGER DEFAULT 1")

    if "can_update" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN can_update INTEGER DEFAULT 1")

    if "is_admin" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

def ensure_admin_exists():
    conn = get_db()
    admin = conn.execute(
        "SELECT * FROM users WHERE role='admin'"
    ).fetchone()

    if not admin:
        conn.execute(
            """
            INSERT INTO users (name, email, password, role, is_admin)
            VALUES ('Admin', 'admin@gmail.com', '1234', 'admin', 1)
            """
        )
        conn.commit()

    conn.close()



# ---------------------------
# Public Enquiry Form
# ---------------------------
@app.route("/", methods=["GET", "POST"])
def enquiry():
    if request.method == "POST":
        company = request.form["company"]
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        message = request.form["message"]

        conn = get_db()
        conn.execute(
            """
            INSERT INTO enquiries (company, name, phone, email, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (company, name, phone, email, message),
        )
        conn.commit()
        conn.close()

        return redirect("/thank-you")

    return render_template("enquiry.html")



@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html", version=APP_VERSION)

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
    if not is_admin_user():
        return redirect("/admin/login")

    conn = get_db()

    enquiries = conn.execute("""
        SELECT 
            e.*, 
            u.name AS sales_name
        FROM enquiries e
        LEFT JOIN users u ON e.assigned_to = u.id
        ORDER BY e.created_at DESC
    """).fetchall()

    conn.close()

    return render_template("admin_dashboard.html", enquiries=enquiries,version=APP_VERSION)




@app.route("/admin/assign/<int:enquiry_id>", methods=["GET", "POST"])
def assign_enquiry(enquiry_id):
    if not is_admin_user():
        return redirect("/admin/login")

    conn = get_db()

    if request.method == "POST":
        sales_id = request.form.get("sales_id")

        conn.execute(
            """
            UPDATE enquiries
            SET assigned_to=?, status='Assigned', assigned_at=?
            WHERE id=?
            """,
            (sales_id, datetime.now(), enquiry_id),
        )

        conn.commit()
        conn.close()
        return redirect("/admin/dashboard")

    enquiry = conn.execute("""
        SELECT e.*, u.name AS sales_name
        FROM enquiries e
        LEFT JOIN users u ON e.assigned_to = u.id
        WHERE e.id=?
    """, (enquiry_id,)).fetchone()

    sales_users = conn.execute(
        "SELECT id, name FROM users WHERE role='sales'"
    ).fetchall()

    conn.close()

    return render_template(
        "assign.html",
        enquiry=enquiry,
        sales_users=sales_users,
        version=APP_VERSION
    )



@app.route("/admin/add-sales", methods=["GET", "POST"])
def add_sales():
    if not is_admin_user():
        return redirect("/admin/login")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        can_view = 1 if request.form.get("can_view") else 0
        can_update = 1 if request.form.get("can_update") else 0
        is_admin = 1 if request.form.get("is_admin") else 0

        if not name or not email or not password:
            return "All fields are required", 400

        conn = get_db()

        try:
            conn.execute(
                """
                INSERT INTO users
                (name, email, password, role, can_view, can_update, is_admin)
                VALUES (?, ?, ?, 'sales', ?, ?, ?)
                """,
                (name, email, password, can_view, can_update, is_admin),
            )
            conn.commit()
        except Exception as e:
            conn.close()
            return f"Error: {str(e)}"

        conn.close()
        return redirect("/admin/dashboard")

    return render_template("add_sales.html",version=APP_VERSION)

@app.route("/admin/view/<int:enquiry_id>")
def admin_view_enquiry(enquiry_id):
    if not is_admin_user():
        return redirect("/admin/login")

    conn = get_db()
    enquiry = conn.execute(
        "SELECT * FROM enquiries WHERE id=?",
        (enquiry_id,),
    ).fetchone()
    conn.close()

    if not enquiry:
        return "Enquiry not found", 404

    return render_template("admin_view.html", enquiry=enquiry, version=APP_VERSION)

@app.route("/admin/report/<int:enquiry_id>")
def admin_view_report(enquiry_id):
    if not is_admin_user():
        return redirect("/admin/login")

    conn = get_db()
    enquiry = conn.execute("""
        SELECT e.*, u.name AS sales_name
        FROM enquiries e
        LEFT JOIN users u ON e.assigned_to = u.id
        WHERE e.id=?
    """, (enquiry_id,)).fetchone()
    conn.close()

    return render_template("admin_report.html", enquiry=enquiry,version=APP_VERSION)



@app.route("/admin/report/pdf/<int:enquiry_id>")
def export_report_pdf(enquiry_id):
    if not is_admin_user():
        return redirect("/admin/login")

    conn = get_db()
    enquiry = conn.execute("""
        SELECT e.*, u.name AS sales_name
        FROM enquiries e
        LEFT JOIN users u ON e.assigned_to = u.id
        WHERE e.id=?
    """, (enquiry_id,)).fetchone()
    conn.close()

    if not enquiry:
        return "Report not found", 404

    # File path
    filename = f"report_file_{enquiry_id}.pdf"
    filepath = os.path.join("static", filename)

    # Create PDF
    doc = SimpleDocTemplate(filepath)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Enquiry Report", styles['Title']))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>Company:</b> {enquiry['company']}", styles['Normal']))
    story.append(Paragraph(f"<b>Name:</b> {enquiry['name']}", styles['Normal']))
    story.append(Paragraph(f"<b>Phone:</b> {enquiry['phone']}", styles['Normal']))
    story.append(Paragraph(f"<b>Email:</b> {enquiry['email']}", styles['Normal']))
    story.append(Paragraph(f"<b>Requirement:</b> {enquiry['message']}", styles['Normal']))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>Created At:</b> {enquiry['created_at']}", styles['Normal']))
    story.append(Paragraph(f"<b>Assigned To:</b> {enquiry['sales_name']}", styles['Normal']))
    story.append(Paragraph(f"<b>Assigned At:</b> {enquiry['assigned_at']}", styles['Normal']))
    story.append(Spacer(1, 12))

    status = "Completed" if enquiry["completed"] else "Not Completed"
    story.append(Paragraph(f"<b>Status:</b> {status}", styles['Normal']))
    story.append(Paragraph(f"<b>Outcome:</b> {enquiry['outcome'] or 'N/A'}", styles['Normal']))
    story.append(Paragraph(f"<b>Report Generated At:</b> {enquiry['report_created_at']}", styles['Normal']))

    doc.build(story)

    return send_file(filepath, as_attachment=True)






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
        """
        SELECT *
        FROM enquiries
        WHERE assigned_to=?
        ORDER BY assigned_at DESC
        """,
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

@app.route("/sales/report/<int:enquiry_id>", methods=["GET", "POST"])
def generate_report(enquiry_id):
    if "sales" not in session:
        return redirect("/sales/login")

    conn = get_db()

    enquiry = conn.execute(
        "SELECT * FROM enquiries WHERE id=? AND assigned_to=?",
        (enquiry_id, session["sales"]),
    ).fetchone()

    if not enquiry:
        conn.close()
        return "Unauthorized", 403

    if request.method == "POST":
        completed = 1 if request.form.get("completed") else 0
        outcome = request.form.get("outcome")

        from datetime import datetime

        conn.execute(
            """
            UPDATE enquiries
            SET completed=?, outcome=?, report_created_at=?
            WHERE id=?
            """,
            (completed, outcome, datetime.now(), enquiry_id),
        )
        conn.commit()
        conn.close()

        return redirect("/sales/dashboard")

    conn.close()
    return render_template("report_form.html", enquiry=enquiry, version=APP_VERSION)



if __name__ == "__main__":
    app.run()

# Required for Render
app = app
