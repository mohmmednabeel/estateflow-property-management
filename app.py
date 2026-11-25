from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, date
import mysql.connector
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

def format_inr(amount):
    amount = int(float(amount or 0))
    number = str(amount)

    if len(number) <= 3:
        return number

    last_three = number[-3:]
    remaining = number[:-3]

    groups = []
    while len(remaining) > 2:
        groups.insert(0, remaining[-2:])
        remaining = remaining[:-2]

    if remaining:
        groups.insert(0, remaining)

    return ",".join(groups + [last_three])


app.jinja_env.filters["inr"] = format_inr


def properties_home():
    if session.get("role") == "owner":
        return redirect(url_for("owner_dashboard"))

    return redirect(url_for("properties"))


app.jinja_env.globals["properties_home"] = properties_home

UPLOAD_FOLDER = os.path.join(
    app.root_path, "static", "uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access EstateFlow.", "error")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                    flash("You do not have permission to access this page.", "error")
                    return redirect(url_for("role_home"))

            return view(*args, **kwargs)
        return wrapped_view
    return decorator

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))




@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone_number = request.form.get("phone_number", "").strip()
        role = request.form.get("role", "user").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate required fields
        if not name or not email or not password or not confirm_password:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("register"))

        if role not in ("owner", "user"):
            flash("Invalid account type selected.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (email,)
            )

            if cursor.fetchone():
                flash("This email is already registered. Please log in.", "error")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)

            
            cursor.execute("""
                INSERT INTO users (full_name, email, phone_number, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, email, phone_number, password_hash, role))

            connection.commit()

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.Error as error:
            if connection:
                connection.rollback()

            print("Registration database error:", error)
            flash("Could not create your account. Please check the server error.", "error")
            return redirect(url_for("register"))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("role_home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT user_id, full_name, email, password_hash, role
                FROM users
                WHERE email = %s
            """, (email,))

            user = cursor.fetchone()

            if user and check_password_hash(
                user["password_hash"], password
            ):
                session.clear()
                session["user_id"] = user["user_id"]
                session["user_name"] = user["full_name"]
                session["user_email"] = user["email"]
                session["role"] = user["role"]

                return redirect(url_for("role_home"))

            flash("Invalid email or password.", "error")

        except mysql.connector.Error as error:
            print("Login database error:", error)
            flash("Could not log in. Please try again.", "error")

        finally:
            if cursor is not None:
                cursor.close()

            if connection is not None and connection.is_connected():
                connection.close()

    return render_template("login.html")





@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))
    return render_template("login.html")




@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("forgot_password"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("forgot_password"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("forgot_password"))

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()

            if not user:
                flash("No account found with that email.", "error")
                return redirect(url_for("forgot_password"))

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE user_id = %s
                """,
                (password_hash, user[0])
            )

            connection.commit()

            flash("Password updated successfully! Please log in.", "success")
            return redirect(url_for("login"))

        except mysql.connector.Error as error:
            print("Password reset database error:", error)
            flash("Could not reset your password. Please try again.", "error")

        finally:
            if cursor is not None:
                cursor.close()

            if connection is not None and connection.is_connected():
                connection.close()

    return render_template("forgot_password.html")

@app.route("/admin-dashboard")
@login_required
def admin_dashboard():
    if session.get("role") != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("role_home"))

    return redirect(url_for("dashboard"))



@app.route("/owner-dashboard")
@login_required
def owner_dashboard():
    if session.get("role") != "owner":
        flash("Access denied. Owner only.", "error")
        return redirect(url_for("role_home"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        owner_id = session["user_id"]

        # Count this owner's properties
        cursor.execute("""
            SELECT
                COUNT(*) AS total_properties,
                SUM(CASE
                    WHEN availability = 'Available' THEN 1
                    ELSE 0
                END) AS available_properties
            FROM properties
            WHERE owner_id = %s
        """, (owner_id,))

        stats = cursor.fetchone()

        # Fetch only this owner's property listings
        cursor.execute("""
            SELECT *
            FROM properties
            WHERE owner_id = %s
            ORDER BY property_id DESC
        """, (owner_id,))

        property_list = cursor.fetchall()

        # Fetch all photos for each property
        for property_item in property_list:
            cursor.execute("""
                SELECT photo_path
                FROM property_photos
                WHERE property_id = %s
                ORDER BY photo_id ASC
            """, (property_item["property_id"],))

            photo_rows = cursor.fetchall()
            property_item["photos"] = [
                photo["photo_path"] for photo in photo_rows
            ]

        return render_template(
            "owner_dashboard.html",
            properties=property_list,
            stats=stats
        )

    except mysql.connector.Error as error:
        print("Owner dashboard database error:", error)
        flash("Could not load your properties.", "error")

        return render_template(
            "owner_dashboard.html",
            properties=[],
            stats={
                "total_properties": 0,
                "available_properties": 0
            }
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
            

@app.route("/owner-enquiries")
@login_required
def owner_enquiries():
    if session.get("role") != "owner":
        flash("Only property owners can access these enquiries.", "error")
        return redirect(url_for("role_home"))

    connection = None
    cursor = None
    enquiries = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                e.enquiry_id,
                e.property_id,
                e.user_id,                
                e.message,
                e.status,
                e.reply_message,
                e.buyer_status,
                e.buyer_message,
                e.created_at,
                p.title AS property_title,
                p.city,
                u.full_name AS buyer_name,
                u.email AS buyer_email,
                u.phone_number AS buyer_phone
            FROM enquiries e
            JOIN properties p ON e.property_id = p.property_id
            JOIN users u ON e.user_id = u.user_id
            WHERE p.owner_id = %s
            ORDER BY e.created_at DESC
        """, (session["user_id"],))

        enquiries = cursor.fetchall()
        
        cursor.execute("""
            SELECT
                sv.visit_id,
                sv.visit_date,
                sv.visit_time,
                sv.status,
                sv.message,
                p.title AS property_title,
                p.city,
                u.full_name AS buyer_name,
                u.email AS buyer_email
            FROM site_visits sv
            JOIN properties p ON p.property_id = sv.property_id
            JOIN users u ON u.user_id = sv.buyer_id
            WHERE sv.owner_id = %s
            ORDER BY sv.visit_date DESC, sv.visit_time DESC
        """, (session["user_id"],))

        visits = cursor.fetchall()

    except mysql.connector.Error as error:
        print("Owner enquiries error:", error)
        flash("Could not load enquiries.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    
    return render_template("owner_enquiries.html",enquiries=enquiries,visits=visits,now_date=date.today().isoformat())


@app.route("/owner-enquiries/<int:enquiry_id>/respond", methods=["POST"])
@login_required
def respond_to_enquiry(enquiry_id):
    if session.get("role") != "owner":
        flash("Only property owners can respond to enquiries.", "error")
        return redirect(url_for("role_home"))

    status = request.form.get("status", "").strip()
    reply_message = request.form.get("reply_message", "").strip()

    if status not in ("Accepted", "Denied"):
        flash("Please select Accept or Deny.", "error")
        return redirect(url_for("owner_enquiries"))

    if not reply_message:
        flash("Please enter a reply message to the buyer.", "error")
        return redirect(url_for("owner_enquiries"))

    if len(reply_message) > 3000:
        flash("Your reply must be 3000 characters or fewer.", "error")
        return redirect(url_for("owner_enquiries"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE enquiries e
            JOIN properties p ON e.property_id = p.property_id
            SET e.status = %s,
                e.reply_message = %s
            WHERE e.enquiry_id = %s
              AND p.owner_id = %s
        """, (
            status,
            reply_message,
            enquiry_id,
            session["user_id"]
        ))

        if cursor.rowcount == 0:
            connection.rollback()
            flash(
                "Enquiry not found, or it has not been changed.",
                "error"
            )
        else:
            connection.commit()
            flash(
                f"Enquiry {status.lower()} successfully!",
                "success"
            )

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        print("Respond to enquiry error:", error)
        flash("Could not save your response. Please try again.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("owner_enquiries"))


@app.route("/user-dashboard")
@login_required
def user_dashboard():
    if session.get("role") != "user":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("role_home"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM properties
            WHERE availability = 'Available'
            ORDER BY created_at DESC
        """)
        properties = cursor.fetchall()

        for property_data in properties:
            cursor.execute("""
                SELECT photo_id, photo_path
                FROM property_photos
                WHERE property_id = %s
                ORDER BY photo_id ASC
            """, (property_data["property_id"],))

            photos = cursor.fetchall()
            property_data["photos"] = [
                photo["photo_path"] for photo in photos
            ]

    except mysql.connector.Error as error:
        print("User dashboard error:", error)
        flash("Could not load properties right now.", "error")
        properties = []

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        "user_dashboard.html",
        properties=properties
    )


@app.route("/property/<int:property_id>")
@login_required
def property_details(property_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM properties
            WHERE property_id = %s
              AND availability = 'Available'
        """, (property_id,))

        property_data = cursor.fetchone()

        if not property_data:
            flash("Property not found or no longer available.", "error")
            return redirect(url_for("user_dashboard"))

        cursor.execute("""
            SELECT photo_id, photo_path
            FROM property_photos
            WHERE property_id = %s
            ORDER BY photo_id ASC
        """, (property_id,))

        property_data["photos"] = cursor.fetchall()

        return render_template(
            "property_details.html",
            property=property_data
        )

    except mysql.connector.Error as error:
        print("Property details error:", error)
        flash("Could not load property details.", "error")
        return redirect(url_for("user_dashboard"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            

@app.route("/property/<int:property_id>/enquiry", methods=["POST"])
@login_required
def send_enquiry(property_id):
    if session.get("role") != "user":
        flash("Only registered users can send enquiries.", "error")
        return redirect(url_for("role_home"))

    message = request.form.get("message", "").strip()

    if not message:
        flash("Please enter a message before sending.", "error")
        return redirect(url_for("property_details", property_id=property_id))

    if len(message) > 3000:
        flash("Your message must be 3000 characters or fewer.", "error")
        return redirect(url_for("property_details", property_id=property_id))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT property_id
            FROM properties
            WHERE property_id = %s
              AND availability = 'Available'
        """, (property_id,))

        if cursor.fetchone() is None:
            flash("This property is no longer available.", "error")
            return redirect(url_for("user_dashboard"))

        cursor.execute("""
            INSERT INTO enquiries (property_id, user_id, message)
            VALUES (%s, %s, %s)
        """, (property_id, session["user_id"], message))

        connection.commit()
        flash("Your enquiry has been sent successfully!", "success")

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        print("Send enquiry error:", error)
        flash("Could not send your enquiry. Please try again.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("property_details", property_id=property_id))


@app.route("/my-enquiries")
@login_required
def my_enquiries():
    if session.get("role") != "user":
        flash("Only buyers can access their enquiries.", "error")
        return redirect(url_for("role_home"))

    connection = None
    cursor = None
    enquiries = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                e.enquiry_id,
                e.message,
                e.status,
                e.reply_message,
                e.buyer_status,
                e.buyer_message,
                e.created_at,
                p.property_id,
                p.title AS property_title,
                p.city
            FROM enquiries e
            JOIN properties p ON e.property_id = p.property_id
            WHERE e.user_id = %s
            ORDER BY e.created_at DESC
        """, (session["user_id"],))

        enquiries = cursor.fetchall()

    except mysql.connector.Error as error:
        print("My enquiries error:", error)
        flash("Could not load your enquiries right now.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template("my_enquiries.html", enquiries=enquiries)


@app.route("/my-enquiries/<int:enquiry_id>/respond", methods=["POST"])
@login_required
def buyer_respond_to_offer(enquiry_id):
    if session.get("role") != "user":
        flash("Only buyers can respond to offers.", "error")
        return redirect(url_for("role_home"))

    buyer_status = request.form.get("buyer_status", "").strip()
    buyer_message = request.form.get("buyer_message", "").strip()

    if buyer_status not in ("Accepted", "Denied"):
        flash("Please choose Accept or Decline.", "error")
        return redirect(url_for("my_enquiries"))

    if not buyer_message:
        flash("Please enter a message to the owner.", "error")
        return redirect(url_for("my_enquiries"))

    if len(buyer_message) > 3000:
        flash("Your message must be 3000 characters or fewer.", "error")
        return redirect(url_for("my_enquiries"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE enquiries
            SET buyer_status = %s,
                buyer_message = %s
            WHERE enquiry_id = %s
              AND user_id = %s
              AND status = 'Accepted'
        """, (
            buyer_status,
            buyer_message,
            enquiry_id,
            session["user_id"]
        ))

        if cursor.rowcount == 0:
            connection.rollback()
            flash(
                "You cannot respond to this enquiry yet, or it no longer exists.",
                "error"
            )
        else:
            connection.commit()
            flash("Your response has been sent to the owner!", "success")

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        print("Buyer response error:", error)
        flash("Could not send your response. Please try again.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("my_enquiries"))

@app.route("/role-home")
@login_required
def role_home():
    role = session.get("role")

    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    elif role == "owner":
        return redirect(url_for("owner_dashboard"))
    else:
        return redirect(url_for("user_dashboard"))



@app.route("/dashboard")
@login_required
def dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Total properties
    cursor.execute("SELECT COUNT(*) AS total_properties FROM properties")
    total_properties = cursor.fetchone()["total_properties"]

    # Available properties
    cursor.execute("""
        SELECT COUNT(*) AS available_properties
        FROM properties
        WHERE availability = 'Available'
    """)
    available_properties = cursor.fetchone()["available_properties"]

    # Total customer enquiries
    cursor.execute("SELECT COUNT(*) AS total_customers FROM customers")
    total_customers = cursor.fetchone()["total_customers"]

    # Upcoming scheduled visits
    cursor.execute("""
        SELECT COUNT(*) AS upcoming_visits
        FROM site_visits
        WHERE status = 'Scheduled'
          AND visit_date >= CURDATE()
    """)
    upcoming_visits = cursor.fetchone()["upcoming_visits"]

    # Recent properties
    cursor.execute("""
        SELECT title AS activity_name, created_at, 'Property Added' AS activity_type
        FROM properties
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_properties = cursor.fetchall()

    # Recent customers
    cursor.execute("""
        SELECT customer_name AS activity_name, created_at, 'Customer Added' AS activity_type
        FROM customers
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_customers = cursor.fetchall()

    # Combine and sort recent activity
    recent_activity = recent_properties + recent_customers
    recent_activity.sort(
        key=lambda item: item["created_at"],
        reverse=True
    )
    recent_activity = recent_activity[:5]

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        total_properties=total_properties,
        available_properties=available_properties,
        total_customers=total_customers,
        upcoming_visits=upcoming_visits,
        recent_activity=recent_activity
    )



@app.route("/add-property", methods=["GET", "POST"])
@login_required
def add_property():
    if session.get("role") not in ("admin", "owner"):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": False,
                "message": "You do not have permission to add properties."
            }), 403

        flash("You do not have permission to add properties.", "error")
        return redirect(url_for("role_home"))

    is_fetch = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        property_type = request.form.get("property_type", "")
        listing_type = request.form.get("listing_type", "")
        price = request.form.get("price", "")
        area = request.form.get("area", "")
        bedrooms = request.form.get("bedrooms", "")
        bathrooms = request.form.get("bathrooms", "")
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        availability = request.form.get("availability", "Available")
        owner_name = request.form.get("owner_name", "").strip()
        description = request.form.get("description", "").strip()
        photos = request.files.getlist("photos")

        owner_id = session["user_id"] if session.get("role") == "owner" else None

        connection = None
        cursor = None

        try:
            # Basic validation
            required_fields = {
                "title": title,
                "property_type": property_type,
                "listing_type": listing_type,
                "price": price,
                "area": area,
                "city": city,
                "address": address,
                "availability": availability
            }

            for field, value in required_fields.items():
                if not value:
                    raise ValueError(f"{field.replace('_', ' ').title()} is required.")

            if float(price) <= 0 or float(area) <= 0:
                raise ValueError("Price and area must be greater than zero.")

            if bedrooms and not bedrooms.isdigit():
                raise ValueError("Bedrooms must be a whole number.")

            if bathrooms and not bathrooms.isdigit():
                raise ValueError("Bathrooms must be a whole number.")

            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
                INSERT INTO properties (
                    title, property_type, listing_type, price,
                    area_sqft, bedrooms, bathrooms, city,
                    address, availability, owner_name, description,
                    owner_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                title, property_type, listing_type, float(price),
                float(area), bedrooms or None, bathrooms or None,
                city, address, availability, owner_name, description,
                owner_id
            )

            cursor.execute(query, values)
            property_id = cursor.lastrowid

            # Save multiple photos
            for photo in photos:
                if photo and photo.filename:
                    if not allowed_image(photo.filename):
                        raise ValueError(
                            "Only PNG, JPG, JPEG and WEBP images are allowed."
                        )

                    original_name = secure_filename(photo.filename)

                    if "." not in original_name:
                        raise ValueError("Invalid image filename.")

                    extension = original_name.rsplit(".", 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{extension}"

                    photo_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], filename
                    )

                    photo.save(photo_path)

                    cursor.execute(
                        """
                        INSERT INTO property_photos (property_id, photo_path)
                        VALUES (%s, %s)
                        """,
                        (property_id, f"uploads/{filename}")
                    )

            connection.commit()

            if is_fetch:
                return jsonify({
                    "success": True,
                    "message": "Property and photos saved successfully!",
                    "property_id": property_id
                }), 201

            flash("Property and photos saved successfully!", "success")

            if session.get("role") == "owner":
                return redirect(url_for("owner_dashboard"))

            return redirect(url_for("properties"))

        except (ValueError, TypeError) as error:
            if connection:
                connection.rollback()

            if is_fetch:
                return jsonify({
                    "success": False,
                    "message": str(error)
                }), 400

            flash(str(error), "error")

        except mysql.connector.Error as error:
            if connection:
                connection.rollback()

            print("Database error:", error)

            if is_fetch:
                return jsonify({
                    "success": False,
                    "message": "Could not save property. Please try again."
                }), 500

            flash("Could not save property. Please check the form.", "error")

        finally:
            if cursor:
                cursor.close()

            if connection and connection.is_connected():
                connection.close()

    return render_template("add_property.html")


@app.route("/properties")
@login_required
def properties():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM properties
            ORDER BY property_id DESC
        """)

        property_list = cursor.fetchall()

        print("PROPERTIES FETCHED:", property_list)
        print("NUMBER OF PROPERTIES:", len(property_list))

        # Fetch photos for each property
        for property_item in property_list:
            cursor.execute("""
                SELECT photo_path
                FROM property_photos
                WHERE property_id = %s
                ORDER BY photo_id ASC
            """, (property_item["property_id"],))

            photo_rows = cursor.fetchall()

            property_item["photos"] = [
                photo["photo_path"] for photo in photo_rows
            ]

        # Return AFTER the loop finishes
        return render_template(
            "properties.html",
            properties=property_list
        )

    except mysql.connector.Error as error:
        print("Error fetching properties:", error)
        flash("Could not load properties from the database.", "error")
        return render_template("properties.html", properties=[])

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
            

@app.route("/edit-property/<int:property_id>", methods=["GET", "POST"])
@login_required
def edit_property(property_id):
    connection = None
    cursor = None
    newly_saved_files = []
    files_to_delete = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        
        # Check that the property exists
        if session.get("role") == "owner":
            cursor.execute(
                "SELECT * FROM properties WHERE property_id = %s AND owner_id = %s",
                (property_id, session["user_id"])
            )
        elif session.get("role") == "admin":
            cursor.execute(
                "SELECT * FROM properties WHERE property_id = %s",
                (property_id,)
            )
        else:
            flash("You do not have permission to edit properties.", "error")
            return redirect(url_for("role_home"))

        property_data = cursor.fetchone()

        if property_data is None:
            flash("Property not found.", "error")
            return redirect(url_for("properties"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            property_type = request.form.get("property_type", "").strip()
            listing_type = request.form.get("listing_type", "").strip()
            price = request.form.get("price", "").strip()
            area_sqft = request.form.get("area_sqft", "").strip()
            bedrooms = request.form.get("bedrooms", "").strip()
            bathrooms = request.form.get("bathrooms", "").strip()
            city = request.form.get("city", "").strip()
            address = request.form.get("address", "").strip()
            availability = request.form.get("availability", "").strip()
            owner_name = request.form.get("owner_name", "").strip()
            description = request.form.get("description", "").strip()

            if not title or not property_type or not listing_type or not price or not city:
                flash("Please fill in all required fields.", "error")

            else:
                try:
                    price = float(price)
                    area_sqft = float(area_sqft) if area_sqft else None
                    bedrooms = int(bedrooms) if bedrooms else None
                    bathrooms = int(bathrooms) if bathrooms else None

                    if price <= 0 or (area_sqft is not None and area_sqft <= 0):
                        raise ValueError()

                    if bedrooms is not None and bedrooms < 0:
                        raise ValueError()

                    if bathrooms is not None and bathrooms < 0:
                        raise ValueError()

                    # Validate new photo file types before updating
                    new_photos = [
                        photo for photo in request.files.getlist("new_photos")
                        if photo and photo.filename.strip()
                    ]

                    if any(not allowed_image(photo.filename) for photo in new_photos):
                        flash("Use JPG, JPEG, PNG or WEBP images only.", "error")
                    else:
                        # Update property details
                        cursor.execute("""
                            UPDATE properties
                            SET title = %s,
                                property_type = %s,
                                listing_type = %s,
                                price = %s,
                                area_sqft = %s,
                                bedrooms = %s,
                                bathrooms = %s,
                                city = %s,
                                address = %s,
                                availability = %s,
                                owner_name = %s,
                                description = %s
                            WHERE property_id = %s
                        """, (
                            title, property_type, listing_type, price,
                            area_sqft, bedrooms, bathrooms, city, address,
                            availability, owner_name, description, property_id
                        ))

                        # Remove only selected photos belonging to this property
                        selected_ids = request.form.getlist("delete_photo_ids")

                        for photo_id in selected_ids:
                            cursor.execute("""
                                SELECT photo_path
                                FROM property_photos
                                WHERE photo_id = %s AND property_id = %s
                            """, (photo_id, property_id))

                            photo_record = cursor.fetchone()

                            if photo_record:
                                files_to_delete.append(photo_record["photo_path"])

                                cursor.execute("""
                                    DELETE FROM property_photos
                                    WHERE photo_id = %s AND property_id = %s
                                """, (photo_id, property_id))

                        # Save newly uploaded photos
                        for photo in new_photos:
                            original_name = secure_filename(photo.filename)
                            unique_name = f"{uuid.uuid4().hex}_{original_name}"

                            save_path = os.path.join(
                                app.config["UPLOAD_FOLDER"],
                                unique_name
                            )

                            photo.save(save_path)
                            newly_saved_files.append(save_path)

                            photo_path = "uploads/" + unique_name

                            cursor.execute("""
                                INSERT INTO property_photos
                                    (property_id, photo_path)
                                VALUES (%s, %s)
                            """, (property_id, photo_path))

                        # Save database changes
                        connection.commit()

                        # Delete removed image files after the commit
                        for old_path in files_to_delete:
                            full_path = os.path.join(
                                app.root_path, "static", old_path
                            )

                            if os.path.isfile(full_path):
                                os.remove(full_path)

                        flash("Property and photos updated successfully!", "success")
                        return properties_home()
                except ValueError:
                    connection.rollback()
                    flash(
                        "Enter valid positive numbers for price and area, "
                        "and non-negative room counts.",
                        "error"
                    )

        # Load existing photos for the edit page
        cursor.execute("""
            SELECT photo_id, photo_path
            FROM property_photos
            WHERE property_id = %s
            ORDER BY photo_id ASC
        """, (property_id,))

        property_photos = cursor.fetchall()

        return render_template(
            "edit_property.html",
            property=property_data,
            property_photos=property_photos
        )

    except mysql.connector.Error as error:
        if connection is not None:
            connection.rollback()

        # Clean up new files if the database operation fails
        for saved_file in newly_saved_files:
            if os.path.isfile(saved_file):
                os.remove(saved_file)

        print("Error editing property:", error)
        flash("Could not update the property.", "error")
        return properties_home()

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
            



@app.route("/delete-property/<int:property_id>", methods=["POST"])
@login_required
def delete_property(property_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check who is allowed to delete this property
        if session.get("role") == "owner":
            cursor.execute(
                "DELETE FROM properties WHERE property_id = %s AND owner_id = %s",
                (property_id, session["user_id"])
            )
        elif session.get("role") == "admin":
            cursor.execute(
                "DELETE FROM properties WHERE property_id = %s",
                (property_id,)
            )
        else:
            flash("You do not have permission to delete properties.", "error")
            return redirect(url_for("role_home"))

        if cursor.rowcount == 0:
            connection.rollback()
            flash("Property not found or you do not have permission to delete it.", "error")
        else:
            connection.commit()
            flash("Property deleted successfully!", "success")

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        print("Delete property error:", error)
        flash("Could not delete the property.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return properties_home()


@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    connection = None
    cursor = None

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        customer_type = request.form.get("customer_type", "")
        requirement = request.form.get("requirement", "").strip()
        budget = request.form.get("budget", "")

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
                INSERT INTO customers (
                    customer_name, phone, email,
                    customer_type, requirement, budget
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            values = (
                customer_name, phone, email or None,
                customer_type, requirement, budget or None
            )

            cursor.execute(query, values)
            connection.commit()

            flash("Customer saved successfully!", "success")
            return redirect(url_for("customers"))

        except mysql.connector.Error as error:
            print("Customer database error:", error)
            flash("Could not save customer. Please check the form.", "error")

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None and connection.is_connected():
                connection.close()

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM customers
            ORDER BY customer_id DESC
        """)

        customer_list = cursor.fetchall()

        return render_template(
            "customers.html",
            customers=customer_list
        )

    except mysql.connector.Error as error:
        print("Error fetching customers:", error)
        flash("Could not load customers from the database.", "error")
        return render_template("customers.html", customers=[])

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()



@app.route("/visits", methods=["GET", "POST"])
@login_required
def visits():
    connection = None
    cursor = None

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        property_name = request.form.get("property_name", "").strip()
        visit_date = request.form.get("visit_date", "")
        visit_time = request.form.get("visit_time", "")
        status = request.form.get("status", "Scheduled")
        notes = request.form.get("notes", "").strip()

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                "SELECT customer_id FROM customers WHERE customer_name = %s LIMIT 1",
                (customer_name,)
            )
            customer = cursor.fetchone()

            cursor.execute(
                "SELECT property_id FROM properties WHERE title = %s LIMIT 1",
                (property_name,)
            )
            property_record = cursor.fetchone()

            if not customer or not property_record:
                flash(
                    "Customer or property not found. Enter names exactly as saved in EstateFlow.",
                    "error"
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO site_visits
                    (customer_id, property_id, visit_date, visit_time, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        customer["customer_id"],
                        property_record["property_id"],
                        visit_date,
                        visit_time,
                        status,
                        notes or None
                    )
                )
                connection.commit()
                flash("Site visit saved successfully!", "success")
                return redirect(url_for("visits"))

        except mysql.connector.Error as error:
            print("Site visit database error:", error)
            flash("Could not save the site visit. Check the database details.", "error")

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None and connection.is_connected():
                connection.close()

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                sv.visit_id,
                c.customer_name,
                p.title AS property_name,
                sv.visit_date,
                sv.visit_time,
                sv.status,
                sv.notes
            FROM site_visits sv
            JOIN customers c ON sv.customer_id = c.customer_id
            JOIN properties p ON sv.property_id = p.property_id
            ORDER BY sv.visit_date DESC, sv.visit_time DESC
        """)

        visit_list = cursor.fetchall()
        
        from datetime import timedelta
        
        for visit in visit_list:
            visit_time = visit["visit_time"]
            
            if isinstance(visit_time, timedelta):
                total_seconds = int(visit_time.total_seconds())
                hours = (total_seconds // 3600) % 24
                minutes = (total_seconds % 3600) // 60
                visit["visit_time_display"] = (
                    f"{hours % 12 or 12:02d}:{minutes:02d} "
                    f"{'AM' if hours < 12 else 'PM'}"
                    )
            else:
                visit["visit_time_display"] = visit_time.strftime("%I:%M %p")

        return render_template("visits.html", visits=visit_list)

    except mysql.connector.Error as error:
        print("Error fetching site visits:", error)
        flash("Could not load site visits from the database.", "error")
        return render_template("visits.html", visits=[])

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()



@app.route("/rentals", methods=["GET", "POST"])
@login_required
def rentals():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":
        tenant_name = request.form["tenant_name"].strip()
        property_name = request.form["property_name"].strip()
        monthly_rent = request.form["monthly_rent"]
        security_deposit = request.form["security_deposit"]
        agreement_start = request.form["agreement_start"]
        agreement_end = request.form["agreement_end"]
        status = request.form["status"]

        cursor.execute(
            "SELECT customer_id FROM customers WHERE customer_name = %s",
            (tenant_name,)
        )
        customer = cursor.fetchone()

        cursor.execute(
            "SELECT property_id FROM properties WHERE title = %s",
            (property_name,)
        )
        property_record = cursor.fetchone()

        if not customer or not property_record:
            flash(
                "Customer or property not found. Enter the exact saved names.",
                "error"
            )
        elif agreement_end < agreement_start:
            flash("Agreement end date must be after the start date.", "error")
        else:
            cursor.execute(
                """
                INSERT INTO rentals
                (customer_id, property_id, monthly_rent, security_deposit,
                 agreement_start, agreement_end, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    customer["customer_id"],
                    property_record["property_id"],
                    monthly_rent,
                    security_deposit,
                    agreement_start,
                    agreement_end,
                    status
                )
            )
            connection.commit()
            flash("Rental saved successfully!", "success")
            cursor.close()
            connection.close()
            return redirect(url_for("rentals"))

    cursor.execute(
        """
        SELECT r.rental_id, c.customer_name AS tenant_name,
               p.title AS property_name, r.monthly_rent,
               r.security_deposit, r.agreement_start,
               r.agreement_end, r.status
        FROM rentals r
        JOIN customers c ON r.customer_id = c.customer_id
        JOIN properties p ON r.property_id = p.property_id
        ORDER BY r.rental_id DESC
        """
    )
    rental_list = cursor.fetchall()
    
    
    cursor.execute("""
        SELECT
            COUNT(*) AS active_rentals,
            COALESCE(SUM(monthly_rent), 0) AS monthly_rent,
            COALESCE(SUM(security_deposit), 0) AS security_deposits
        FROM rentals
        WHERE status = 'Active'
    """)
    rental_summary = cursor.fetchone()

    cursor.close()
    connection.close()
    return render_template("rentals.html",rentals=rental_list,rental_summary=rental_summary)


@app.route("/schedule-site-visit/<int:enquiry_id>", methods=["POST"])
@login_required
def schedule_site_visit(enquiry_id):
    if session.get("role") != "owner":
        flash("Only property owners can schedule site visits.", "error")
        return redirect(url_for("role_home"))

    visit_date = request.form.get("visit_date", "").strip()
    visit_time = request.form.get("visit_time", "").strip()
    message = request.form.get("message", "").strip()

    if not visit_date or not visit_time:
        flash("Please select a visit date and time.", "error")
        return redirect(url_for("owner_enquiries"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT e.enquiry_id, e.property_id, e.user_id,
                   p.owner_id, p.title
            FROM enquiries e
            JOIN properties p ON p.property_id = e.property_id
            WHERE e.enquiry_id = %s
              AND p.owner_id = %s
              AND e.buyer_status = 'Accepted'
              AND e.status = 'Accepted'
        """, (enquiry_id, session["user_id"]))

        enquiry = cursor.fetchone()

        if not enquiry:
            flash("You cannot schedule a visit for this enquiry.", "error")
            return redirect(url_for("owner_enquiries"))

        cursor.execute("""
            INSERT INTO site_visits
                (enquiry_id, property_id, owner_id, buyer_id,
                 visit_date, visit_time, message, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pending')
        """, (
            enquiry["enquiry_id"],
            enquiry["property_id"],
            enquiry["owner_id"],
            enquiry["user_id"],
            visit_date,
            visit_time,
            message,
            message
        ))

        connection.commit()
        flash("Site visit request sent to the buyer!", "success")

    except Exception as error:
        if connection:
            connection.rollback()
        print("Schedule site visit error:", error)
        flash("Could not schedule the site visit. Check the server terminal.", "error")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("owner_enquiries"))


@app.route("/my-site-visits")
@login_required
def my_site_visits():
    if session.get("role") != "user":
        flash("Only buyers can view their site visits.", "error")
        return redirect(url_for("role_home"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                sv.visit_id,
                sv.visit_date,
                sv.visit_time,
                sv.message,
                sv.status,
                p.property_id,
                p.title AS property_title,
                p.city,
                u.full_name AS owner_name,
                u.phone_number AS owner_phone
            FROM site_visits sv
            JOIN properties p ON p.property_id = sv.property_id
            LEFT JOIN users u ON u.user_id = sv.owner_id
            WHERE sv.buyer_id = %s
            ORDER BY sv.visit_date DESC, sv.visit_time DESC
        """, (session["user_id"],))

        visits = cursor.fetchall()

        return render_template("my_site_visits.html", visits=visits)

    except Exception as error:
        print("My site visits error:", error)
        flash("Could not load site visits.", "error")
        return redirect(url_for("user_dashboard"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/respond-site-visit/<int:visit_id>", methods=["POST"])
@login_required
def respond_site_visit(visit_id):
    if session.get("role") != "user":
        flash("Only buyers can respond to site visits.", "error")
        return redirect(url_for("role_home"))

    status = request.form.get("status", "").strip()

    if status not in ("Confirmed", "Declined"):
        flash("Invalid response.", "error")
        return redirect(url_for("my_site_visits"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE site_visits
            SET status = %s
            WHERE visit_id = %s
              AND buyer_id = %s
              AND status = 'Pending'
        """, (status, visit_id, session["user_id"]))

        if cursor.rowcount:
            cursor.execute("""
                SELECT owner_id, property_id
                FROM site_visits
                WHERE visit_id = %s
                  AND buyer_id = %s
            """, (visit_id, session["user_id"]))

            visit = cursor.fetchone()

            if visit:
                owner_id, property_id = visit

                if owner_id:
                    cursor.execute("""
                        SELECT title
                        FROM properties
                        WHERE property_id = %s
                    """, (property_id,))

                    property_row = cursor.fetchone()
                    property_title = (
                        property_row[0]
                        if property_row
                        else "your property"
                    )

                    cursor.execute("""
                        INSERT INTO notifications
                            (user_id, title, message)
                        VALUES (%s, %s, %s)
                    """, (
                        owner_id,
                        "Site Visit Response",
                        f"{session.get('user_name', 'The buyer')} "
                        f"responded to the site visit for "
                        f"{property_title}: {status}."
                    ))

            connection.commit()
            flash(
                "Your site visit response has been submitted.",
                "success"
            )
        else:
            connection.rollback()
            flash(
                "Visit not found or already responded to.",
                "error"
            )

    except Exception as error:
        if connection:
            connection.rollback()

        print("Respond site visit error:", error)
        flash("Could not submit your response.", "error")

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("my_site_visits"))


@app.route("/owner-notifications")
@login_required
def owner_notifications():
    if session.get("role") != "owner":
        flash("Only owners can view notifications.", "error")
        return redirect(url_for("role_home"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT notification_id, title, message,
                   is_read, created_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (session["user_id"],))

        notifications = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) AS unread_count
            FROM notifications
            WHERE user_id = %s AND is_read = 0
        """, (session["user_id"],))

        unread_count = cursor.fetchone()["unread_count"]

        return render_template(
            "owner_notifications.html",
            notifications=notifications,
            unread_count=unread_count
        )

    except Exception as error:
        print("Owner notifications error:", error)
        flash("Could not load notifications.", "error")
        return redirect(url_for("owner_dashboard"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            

@app.route("/admin-site-visits")
@role_required("admin")
def admin_site_visits():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                sv.visit_id,
                sv.visit_date,
                sv.visit_time,
                sv.status,
                sv.notes,
                sv.message,
                p.title AS property_title,
                p.address AS property_address,
                buyer.full_name AS buyer_name,
                buyer.email AS buyer_email,
                owner.full_name AS owner_name
            FROM site_visits sv
            JOIN properties p
                ON sv.property_id = p.property_id
            JOIN users buyer
                ON sv.buyer_id = buyer.user_id
            LEFT JOIN users owner
                ON sv.owner_id = owner.user_id
            ORDER BY sv.visit_date DESC, sv.visit_time DESC
        """)

        visits = cursor.fetchall()

        return render_template(
            "admin_site_visits.html",
            visits=visits
        )

    finally:
        cursor.close()
        connection.close()
        

@app.route("/api/properties", methods=["GET"])
@login_required
def api_get_properties():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT property_id, title, property_type, listing_type,
                   price, area_sqft, bedrooms, bathrooms, city, address,
                   availability, owner_name, description, created_at
            FROM properties
            ORDER BY property_id DESC
        """)

        properties = cursor.fetchall()

        for prop in properties:
            cursor.execute("""
                SELECT photo_path
                FROM property_photos
                WHERE property_id = %s
                ORDER BY photo_id ASC
            """, (prop["property_id"],))

            photo_rows = cursor.fetchall()

            prop["photos"] = [
                photo["photo_path"] for photo in photo_rows
            ]

            if prop.get("created_at"):
                prop["created_at"] = prop["created_at"].isoformat()

            if prop.get("price") is not None:
                prop["price"] = float(prop["price"])

            if prop.get("area_sqft") is not None:
                prop["area_sqft"] = float(prop["area_sqft"])

        return jsonify({
            "success": True,
            "count": len(properties),
            "data": properties
        }), 200

    except mysql.connector.Error as error:
        print("API get properties error:", error)

        return jsonify({
            "success": False,
            "message": "Could not fetch properties"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

            
@app.route("/api/properties", methods=["POST"])
def api_add_property():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "message": "Please send valid JSON data"
        }), 400

    # Get data from JSON
    title = data.get("title")
    property_type = data.get("property_type")
    listing_type = data.get("listing_type")
    price = data.get("price")
    area_sqft = data.get("area_sqft")
    bedrooms = data.get("bedrooms")
    bathrooms = data.get("bathrooms")
    city = data.get("city")
    address = data.get("address", "")
    availability = data.get("availability", "Available")
    owner_name = data.get("owner_name", "")
    description = data.get("description", "")

    # Check required fields
    if not all([
    isinstance(title, str) and title.strip(),
    isinstance(property_type, str) and property_type.strip(),
    isinstance(listing_type, str) and listing_type.strip(),
    price is not None and price != "",
    isinstance(city, str) and city.strip(),
    isinstance(address, str) and address.strip(),
    isinstance(owner_name, str) and owner_name.strip(),
    isinstance(description, str) and description.strip()
        ]):
     return jsonify({
        "success": False,
        "message": "Title, property type, listing type, price, city, address, owner name and description are required"
    }), 400

    try:
        price = float(price)
        area_sqft = float(area_sqft) if area_sqft is not None else None
        if bedrooms not in (None, ""):
            
            if not str(bedrooms).isdigit():
                raise ValueError("Bedrooms must be a whole number")
            bedrooms = int(bedrooms)
        else:
            bedrooms = None

        if bathrooms not in (None, ""):
            if not str(bathrooms).isdigit():
                raise ValueError("Bathrooms must be a whole number")
                bathrooms = int(bathrooms)
            else:
                bathrooms = None
        area_sqft = (
            float(area_sqft)
            if area_sqft not in (None, "")
            else None
        )

        if price <= 0 or (area_sqft is not None and area_sqft <= 0):
            raise ValueError()

        if bedrooms is not None and bedrooms < 0:
            raise ValueError()

        if bathrooms is not None and bathrooms < 0:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Please enter valid numeric property details"
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        owner_id = (
            session["user_id"]
            if session.get("role") == "owner"
            else None
        )

        cursor.execute("""
            INSERT INTO properties (
                title, property_type, listing_type, price,
                area_sqft, bedrooms, bathrooms, city,
                address, availability, owner_name, description,
                owner_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            title, property_type, listing_type, price,
            area_sqft, bedrooms, bathrooms, city,
            address, availability, owner_name, description,
            owner_id
        ))

        property_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Property added successfully",
            "property_id": property_id
        }), 201

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        print("API add property error:", error)

        return jsonify({
            "success": False,
            "message": "Could not add property"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
            
@app.route("/api/properties/<int:property_id>", methods=["GET"])
def api_get_single_property(property_id):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT property_id, title, property_type, listing_type,
                   price, area_sqft, bedrooms, bathrooms, city, address,
                   availability, owner_name, description, created_at
            FROM properties
            WHERE property_id = %s
        """, (property_id,))

        property_data = cursor.fetchone()

        if property_data is None:
            return jsonify({
                "success": False,
                "message": "Property not found"
            }), 404

        if property_data.get("created_at"):
            property_data["created_at"] = property_data["created_at"].isoformat()

        if property_data.get("price") is not None:
            property_data["price"] = float(property_data["price"])

        if property_data.get("area_sqft") is not None:
            property_data["area_sqft"] = float(property_data["area_sqft"])

        return jsonify({
            "success": True,
            "data": property_data
        }), 200

    except mysql.connector.Error as error:
        print("API single property error:", error)

        return jsonify({
            "success": False,
            "message": "Could not fetch property"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
            

@app.route("/api/properties/<int:property_id>", methods=["PUT"])
@login_required
def api_update_property(property_id):
    connection = None
    cursor = None
    newly_saved_files = []
    files_to_delete = []

    try:
        # Check role and property ownership
        if session.get("role") not in ("admin", "owner"):
            return jsonify({
                "success": False,
                "message": "You do not have permission to edit properties."
            }), 403

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if session.get("role") == "owner":
            cursor.execute("""
                SELECT property_id FROM properties
                WHERE property_id = %s AND owner_id = %s
            """, (property_id, session["user_id"]))
        else:
            cursor.execute("""
                SELECT property_id FROM properties
                WHERE property_id = %s
            """, (property_id,))

        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Property not found or access denied."
            }), 404

        # Read multipart FormData
        title = request.form.get("title", "").strip()
        property_type = request.form.get("property_type", "").strip()
        listing_type = request.form.get("listing_type", "").strip()
        price = request.form.get("price", "").strip()
        area_sqft = request.form.get("area_sqft", "").strip()
        bedrooms = request.form.get("bedrooms", "").strip()
        bathrooms = request.form.get("bathrooms", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        availability = request.form.get("availability", "").strip()
        owner_name = request.form.get("owner_name", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, property_type, listing_type, price, city]):
            return jsonify({
                "success": False,
                "message": "Please fill in all required fields."
            }), 400

        try:
            price = float(price)
            area_sqft = float(area_sqft) if area_sqft else None
            bedrooms = int(bedrooms) if bedrooms else None
            bathrooms = int(bathrooms) if bathrooms else None

            if price <= 0 or (area_sqft is not None and area_sqft <= 0):
                raise ValueError()

            if bedrooms is not None and bedrooms < 0:
                raise ValueError()

            if bathrooms is not None and bathrooms < 0:
                raise ValueError()

        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": "Enter valid positive price/area and non-negative room counts."
            }), 400

        new_photos = [
            photo for photo in request.files.getlist("new_photos")
            if photo and photo.filename.strip()
        ]

        for photo in new_photos:
            if not allowed_image(photo.filename):
                return jsonify({
                    "success": False,
                    "message": "Use JPG, JPEG, PNG or WEBP images only."
                }), 400

        # Update property details
        cursor.execute("""
            UPDATE properties
            SET title = %s,
                property_type = %s,
                listing_type = %s,
                price = %s,
                area_sqft = %s,
                bedrooms = %s,
                bathrooms = %s,
                city = %s,
                address = %s,
                availability = %s,
                owner_name = %s,
                description = %s
            WHERE property_id = %s
        """, (
            title, property_type, listing_type, price,
            area_sqft, bedrooms, bathrooms, city,
            address, availability, owner_name, description,
            property_id
        ))

        # Delete only selected photos belonging to this property
        for photo_id in request.form.getlist("delete_photo_ids"):
            if not photo_id.isdigit():
                continue

            cursor.execute("""
                SELECT photo_path FROM property_photos
                WHERE photo_id = %s AND property_id = %s
            """, (int(photo_id), property_id))

            photo_record = cursor.fetchone()

            if photo_record:
                files_to_delete.append(photo_record["photo_path"])

                cursor.execute("""
                    DELETE FROM property_photos
                    WHERE photo_id = %s AND property_id = %s
                """, (int(photo_id), property_id))

        # Save new photos
        for photo in new_photos:
            original_name = secure_filename(photo.filename)
            extension = original_name.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{extension}"

            save_path = os.path.join(
                app.config["UPLOAD_FOLDER"], filename
            )

            photo.save(save_path)
            newly_saved_files.append(save_path)

            cursor.execute("""
                INSERT INTO property_photos (property_id, photo_path)
                VALUES (%s, %s)
            """, (property_id, f"uploads/{filename}"))

        connection.commit()

        # Remove old image files only after successful commit
        for old_path in files_to_delete:
            full_path = os.path.join(app.root_path, "static", old_path)
            if os.path.isfile(full_path):
                os.remove(full_path)

        return jsonify({
            "success": True,
            "message": "Property and photos updated successfully!"
        }), 200

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        for saved_file in newly_saved_files:
            if os.path.isfile(saved_file):
                os.remove(saved_file)

        print("API property update error:", error)
        return jsonify({
            "success": False,
            "message": "Could not update property. Please try again."
        }), 500

    except Exception as error:
        if connection:
            connection.rollback()

        for saved_file in newly_saved_files:
            if os.path.isfile(saved_file):
                os.remove(saved_file)

        print("Unexpected property update error:", error)
        return jsonify({
            "success": False,
            "message": "Something went wrong while updating the property."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

            
@app.route("/api/properties/<int:property_id>", methods=["DELETE"])
def api_delete_property(property_id):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM properties WHERE property_id = %s",
            (property_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({
                "success": False,
                "message": "Property not found"
            }), 404

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Property deleted successfully",
            "property_id": property_id
        }), 200

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        print("API delete property error:", error)

        return jsonify({
            "success": False,
            "message": "Could not delete property"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
            
@app.route("/api/properties/<int:property_id>", methods=["PATCH"])
def api_update_property_partially(property_id):

    connection = None
    cursor = None

    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                "success": False,
                "message": "Please send valid JSON data"
            }), 400

        if "price" not in data:
            return jsonify({
                "success": False,
                "message": "Please provide the price"
            }), 400

        try:
            price = float(data["price"])

            if price <= 0:
                raise ValueError()

        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": "Price must be a valid positive number"
            }), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT property_id FROM properties WHERE property_id = %s",
            (property_id,)
        )

        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Property not found"
            }), 404

        cursor.execute(
            "UPDATE properties SET price = %s WHERE property_id = %s",
            (price, property_id)
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Property price updated successfully",
            "property_id": property_id,
            "new_price": price
        }), 200

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        print("API PATCH error:", error)

        return jsonify({
            "success": False,
            "message": "Could not update property"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
            
@app.route('/api/test-json', methods=['POST'])
def test_json():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "message": "Please send valid JSON data"
        }), 400

    name = data.get('name')
    age = data.get('age')

    if not name or age is None:
        return jsonify({
            "success": False,
            "message": "Name and age are required"
        }), 400

    return jsonify({
        "success": True,
        "message": "Data received successfully",
        "name": name,
        "age": age
    }), 200
    
@app.route("/api/customers", methods=["GET"])
def api_get_customers():

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                customer_id,
                customer_name,
                phone,
                email,
                customer_type,
                requirement,
                budget,
                created_at
            FROM customers
            ORDER BY customer_id DESC
        """)

        customers = cursor.fetchall()

        return jsonify({
            "success": True,
            "count": len(customers),
            "data": customers
        }), 200

    except mysql.connector.Error as error:
        print("API get customers error:", error)

        return jsonify({
            "success": False,
            "message": "Could not fetch customers"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
            
@app.route("/api/customers/<int:customer_id>", methods=["GET"])
def api_get_customer(customer_id):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM customers WHERE customer_id = %s",
            (customer_id,)
        )

        customer = cursor.fetchone()

        if not customer:
            return jsonify({
                "success": False,
                "message": "Customer not found"
            }), 404

        return jsonify({
            "success": True,
            "data": customer
        }), 200

    except mysql.connector.Error as error:
        print("API get customer error:", error)
        return jsonify({
            "success": False,
            "message": "Could not fetch customer"
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            
@app.route("/api/customers", methods=["POST"])
def api_add_customer():

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "success": False,
            "message": "Please send valid JSON data"
        }), 400

    customer_name = data.get("customer_name")
    phone = data.get("phone")
    email = data.get("email")
    customer_type = data.get("customer_type")
    requirement = data.get("requirement")
    budget = data.get("budget")

    if not all([
        isinstance(customer_name, str) and customer_name.strip(),
        isinstance(phone, str) and phone.strip(),
        isinstance(customer_type, str) and customer_type.strip(),
        isinstance(requirement, str) and requirement.strip(),
        budget is not None and budget != ""
    ]):
        return jsonify({
            "success": False,
            "message": "Customer name, phone, customer type, requirement and budget are required"
        }), 400

    try:
        budget = float(budget)

        if budget <= 0:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Budget must be a positive number"
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO customers (
                customer_name, phone, email,
                customer_type, requirement, budget
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            customer_name, phone, email,
            customer_type, requirement, budget
        ))

        customer_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Customer added successfully",
            "customer_id": customer_id
        }), 201

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        print("API add customer error:", error)

        return jsonify({
            "success": False,
            "message": "Could not add customer"
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route("/api/customers/<int:customer_id>", methods=["PUT"])
def api_update_customer(customer_id):

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "success": False,
            "message": "Please send valid JSON data"
        }), 400

    customer_name = data.get("customer_name")
    phone = data.get("phone")
    email = data.get("email")
    customer_type = data.get("customer_type")
    requirement = data.get("requirement")
    budget = data.get("budget")

    if not all([
        isinstance(customer_name, str) and customer_name.strip(),
        isinstance(phone, str) and phone.strip(),
        isinstance(customer_type, str) and customer_type.strip(),
        isinstance(requirement, str) and requirement.strip(),
        budget is not None and budget != ""
    ]):
        return jsonify({
            "success": False,
            "message": "Required customer fields are missing"
        }), 400

    try:
        budget = float(budget)

        if budget <= 0:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Budget must be a positive number"
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT customer_id FROM customers WHERE customer_id = %s",
            (customer_id,)
        )

        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Customer not found"
            }), 404

        cursor.execute("""
            UPDATE customers
            SET customer_name = %s,
                phone = %s,
                email = %s,
                customer_type = %s,
                requirement = %s,
                budget = %s
            WHERE customer_id = %s
        """, (
            customer_name, phone, email,
            customer_type, requirement, budget, customer_id
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Customer updated successfully",
            "customer_id": customer_id
        }), 200

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()

        print("API update customer error:", error)

        return jsonify({
            "success": False,
            "message": "Could not update customer"
        }), 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            
@app.route('/api/customers/<int:customer_id>', methods=['DELETE'])
def api_delete_customer(customer_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check whether customer exists
        cursor.execute(
            "SELECT customer_id FROM customers WHERE customer_id = %s",
            (customer_id,)
        )
        customer = cursor.fetchone()

        if not customer:
            return jsonify({
                "success": False,
                "message": "Customer not found"
            }), 404

        # Check whether customer has rental records
        cursor.execute(
            "SELECT rental_id FROM rentals WHERE customer_id = %s LIMIT 1",
            (customer_id,)
        )
        rental = cursor.fetchone()

        if rental:
            return jsonify({
                "success": False,
                "message": "Cannot delete customer because rental records are linked to this customer."
            }), 409

        # Delete customer if no rental records exist
        cursor.execute(
            "DELETE FROM customers WHERE customer_id = %s",
            (customer_id,)
        )

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Customer deleted successfully"
        }), 200

    except Exception as error:
        conn.rollback()
        print("API delete customer error:", error)

        return jsonify({
            "success": False,
            "message": "Something went wrong while deleting customer"
        }), 500

    finally:
        cursor.close()
        conn.close()
        
if __name__ == "__main__":
    app.run(debug=True)