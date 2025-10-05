import os
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

import re
import random
import json
import time
import logging
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
import sys

app = Flask(__name__)

# ------------------ LOGGING SETUP ------------------
# Create handlers with UTF-8 encoding to support emojis
file_handler = logging.FileHandler('app.log', encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        stream_handler
    ]
)
logger = logging.getLogger(__name__)

# ------------------ SECURE CONFIG ------------------
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-CHANGE-IN-PRODUCTION-' + str(random.randint(1000, 9999)))

# Session Configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Flask-Mail Config with detailed debugging
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_USERNAME
app.config['MAIL_DEBUG'] = True
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_ASCII_ATTACHMENTS'] = False

try:
    mail = Mail(app)
    logger.info("✓ Flask-Mail initialized successfully")
except Exception as e:
    logger.error(f"✗ Flask-Mail initialization failed: {e}")

# ------------------ CONSTANTS ------------------
USERS_FILE = 'users.json'
OTP_EXPIRY_SECONDS = 600
OTP_LENGTH = 6
MAX_OTP_ATTEMPTS = 3

rate_limit_storage = {}


# ------------------ VALIDATION HELPERS ------------------
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone):
    pattern = r'^\+?1?\d{10,15}$'
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(pattern, cleaned))


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[\W_]', password):
        return False, "Password must contain at least one special character"
    return True, "Valid password"


def validate_user_input(email_mobile):
    email_mobile = email_mobile.strip()
    if '@' in email_mobile:
        if validate_email(email_mobile):
            return 'email', email_mobile
        return None, "Invalid email format"
    else:
        if validate_phone(email_mobile):
            return 'phone', email_mobile
        return None, "Invalid phone number format"


# ------------------ RATE LIMITING ------------------
def check_rate_limit(key, max_attempts=5, window=3600):
    current_time = time.time()
    if key not in rate_limit_storage:
        rate_limit_storage[key] = []

    rate_limit_storage[key] = [
        timestamp for timestamp in rate_limit_storage[key]
        if current_time - timestamp < window
    ]

    if len(rate_limit_storage[key]) >= max_attempts:
        return False, f"Too many attempts. Please try again later."

    rate_limit_storage[key].append(current_time)
    return True, "OK"


# ------------------ DATABASE FUNCTIONS ------------------
def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except json.JSONDecodeError:
        logger.error("Corrupted users.json file")
    except Exception as e:
        logger.error(f"Error loading users: {e}")
    return {}


def save_users(users_dict):
    try:
        temp_file = f"{USERS_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(users_dict, f, indent=2)
        os.replace(temp_file, USERS_FILE)
        logger.info("Users data saved successfully")
    except Exception as e:
        logger.error(f"Error saving users: {e}")
        raise


users = load_users()


# ------------------ AUTHENTICATION DECORATOR ------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash("Please login to access this page", "warning")
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# ------------------ HELPER FUNCTIONS ------------------
def resolve_image_path(rel_path):
    static_root = app.static_folder
    if not static_root:
        return 'images/placeholder.jpg'

    cand_paths = [rel_path]
    dirname = os.path.dirname(rel_path)
    filename = os.path.basename(rel_path)
    name_no_ext, ext = os.path.splitext(filename)

    tries = [
        filename, filename.lower(),
        filename.replace(" ", "_"),
        filename.replace(" ", "_").lower(),
        name_no_ext.replace(" ", "_") + ext,
        name_no_ext.replace(" ", "_").lower() + ext,
        name_no_ext.title() + ext,
    ]

    for t in tries:
        cand_paths.append(os.path.join(dirname, t))
    for t in tries:
        cand_paths.append(t)

    seen, final_cands = set(), []
    for p in cand_paths:
        if p not in seen:
            final_cands.append(p)
            seen.add(p)

    for p in final_cands:
        full = os.path.join(static_root, p)
        if os.path.exists(full):
            return p
    return 'images/placeholder.jpg'


# ------------------ OTP FUNCTIONS ------------------
def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(OTP_LENGTH)])


def send_otp_email(recipient, otp, purpose="authentication"):
    """Send OTP via email with comprehensive error handling"""
    try:
        # Validate email config
        if not MAIL_USERNAME or MAIL_USERNAME == 'youremail@gmail.com':
            logger.error("✗ MAIL_USERNAME not configured in .env file")
            logger.error("Please create a .env file with your Gmail address")
            return False, "Email not configured. Using development OTP."

        if not MAIL_PASSWORD or MAIL_PASSWORD == 'yourapppassword':
            logger.error("✗ MAIL_PASSWORD not configured in .env file")
            logger.error("Please create a Gmail App Password and add it to .env")
            return False, "Email password not configured. Using development OTP."

        logger.info(f"📧 Preparing to send OTP to: {recipient}")
        logger.info(f"📤 Using sender: {MAIL_USERNAME}")
        logger.info(f"🔑 Password length: {len(MAIL_PASSWORD)} characters")

        subject = "Cardwala - Your OTP Code"
        if purpose == "login":
            subject = "Cardwala - Login OTP"
        elif purpose == "signup":
            subject = "Cardwala - Signup OTP"

        msg = Message(
            subject=subject,
            recipients=[recipient],
            body=f"""Hello,

Your OTP code is: {otp}

This code is valid for {OTP_EXPIRY_SECONDS // 60} minutes.
Please do not share this code with anyone.

If you didn't request this code, please ignore this email.

Best regards,
Cardwala Team"""
        )

        logger.info("📨 Sending email via SMTP...")
        mail.send(msg)
        logger.info(f"✅ SUCCESS! OTP email sent to {recipient}")
        return True, "OTP sent to your email"

    except smtplib.SMTPAuthenticationError as e:
        logger.error("=" * 60)
        logger.error("✗ SMTP AUTHENTICATION FAILED!")
        logger.error("=" * 60)
        logger.error(f"Error details: {str(e)}")
        logger.error("")
        logger.error("TROUBLESHOOTING STEPS:")
        logger.error("1. Make sure you're using a Gmail App Password, NOT your regular password")
        logger.error("2. Enable 2-Step Verification: https://myaccount.google.com/security")
        logger.error("3. Generate App Password: https://myaccount.google.com/apppasswords")
        logger.error("4. Copy the 16-character password (remove spaces)")
        logger.error("5. Add it to your .env file as MAIL_PASSWORD=yourapppassword")
        logger.error("")
        logger.error(f"Current MAIL_USERNAME: {MAIL_USERNAME}")
        logger.error(f"Password configured: {'Yes' if MAIL_PASSWORD else 'No'}")
        logger.error("=" * 60)
        return False, "Email authentication failed"

    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"✗ Invalid recipient email: {recipient}")
        logger.error(f"Error: {str(e)}")
        return False, "Invalid email address"

    except smtplib.SMTPException as e:
        logger.error(f"✗ SMTP Error: {str(e)}")
        return False, "Failed to send email"

    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
        logger.exception(e)
        return False, "Email service error"


def verify_otp_attempt(entered_otp):
    stored_otp = session.get('otp')
    otp_expiry = session.get('otp_expiry')
    attempts = session.get('otp_attempts', 0)

    if not stored_otp or not otp_expiry:
        return False, "Session expired. Please try again."

    if time.time() > otp_expiry:
        session.pop('otp', None)
        session.pop('otp_expiry', None)
        return False, "OTP expired. Please request a new one."

    if attempts >= MAX_OTP_ATTEMPTS:
        session.pop('otp', None)
        session.pop('otp_expiry', None)
        return False, "Maximum OTP attempts exceeded. Please request a new one."

    if entered_otp != stored_otp:
        session['otp_attempts'] = attempts + 1
        remaining = MAX_OTP_ATTEMPTS - session['otp_attempts']
        return False, f"Invalid OTP. {remaining} attempt(s) remaining."

    return True, "OTP verified successfully"


# ------------------ DATA ------------------
religions = [
    {"name": "Hinduism", "image": "images/Religion/Hinduism.jpg"},
    {"name": "Christianity", "image": "images/Religion/christianity.jpg"},
    {"name": "Islam", "image": "images/Religion/Islam.jpg"},
    {"name": "Buddhism", "image": "images/Religion/buddhism.jpg"},
    {"name": "Judaism", "image": "images/Religion/Judaism.jpg"},
    {"name": "Sikhism", "image": "images/Religion/Sikhism.png"},
    {"name": "Taoism", "image": "images/Religion/Taoism_Chinese_Traditions.jpg"},
    {"name": "Zoroastrianism", "image": "images/Religion/Zoroastrianism.jpg"},
]

ceremonies = [
    {"name": "Vivah (Wedding)", "image": "images/Ceremony/Vivah_Wedding.jpg"},
    {"name": "Christian Wedding", "image": "images/Ceremony/Wedding_Christian.jpg"},
    {"name": "Engagement", "image": "images/Ceremony/Engagement.jpg"},
    {"name": "Namkaran", "image": "images/Ceremony/Namkaran.jpg"},
    {"name": "Baptism", "image": "images/Ceremony/Baptism.jpg"},
    {"name": "Confirmation", "image": "images/Ceremony/Confirmation.jpg"},
    {"name": "Annaprashan", "image": "images/Ceremony/annaprashan.jpg"},
    {"name": "Mundan", "image": "images/Ceremony/Mundan.jpg"},
    {"name": "Upanayana", "image": "images/Ceremony/Upanayana.jpg"},
    {"name": "Grihapravesh", "image": "images/Ceremony/Grihapravesh.jpg"},
    {"name": "Shraddha", "image": "images/Ceremony/Shraddha.jpg"},
]


# ------------------ ROUTES ------------------

@app.route("/")
def index():
    rels = [{**r, "image": resolve_image_path(r["image"])} for r in religions]
    cers = [{**c, "image": resolve_image_path(c["image"])} for c in ceremonies]

    show_otp = session.get('otp_sent', False)
    signup_mode = session.get('signup_mode', False)
    email_mobile = session.get('email_mobile', '')

    return render_template("index.html",
                           religions=rels,
                           ceremonies=cers,
                           show_otp=show_otp,
                           signup_mode=signup_mode,
                           email_mobile=email_mobile)


@app.route("/generate-captcha/<captcha_type>")
def generate_captcha_api(captcha_type):
    if captcha_type not in ['signup', 'login']:
        return jsonify({'error': 'Invalid captcha type'}), 400

    captcha_code = str(random.randint(10000, 99999))
    session[f"captcha_{captcha_type}"] = captcha_code
    logger.info(f"Generated captcha for {captcha_type}: {captcha_code}")
    return jsonify({'captcha': captcha_code})


@app.route("/create-card", methods=["POST"])
def create_card():
    religion = request.form.get("religion")
    ceremony = request.form.get("ceremony")

    if not religion or not ceremony:
        flash("Please select both religion and ceremony!", "error")
        return redirect(url_for("index"))

    session['selected_religion'] = religion
    session['selected_ceremony'] = ceremony
    flash(f"Creating card for {religion} - {ceremony}", "success")
    return redirect(url_for("customize_card"))


@app.route("/customize-card")
@login_required
def customize_card():
    religion = session.get('selected_religion', 'Not selected')
    ceremony = session.get('selected_ceremony', 'Not selected')
    return render_template("customize_card.html", religion=religion, ceremony=ceremony)


@app.route("/signup", methods=["POST"])
def signup():
    email_mobile = request.form.get("email_mobile", "").strip()
    captcha = request.form.get("captcha", "").strip()
    stored_captcha = session.get("captcha_signup", "")

    rate_key = f"signup_{request.remote_addr}"
    can_proceed, message = check_rate_limit(rate_key, max_attempts=5, window=3600)
    if not can_proceed:
        flash(message, "error")
        return redirect(url_for("index"))

    if captcha != stored_captcha:
        logger.warning(f"Signup captcha failed for {email_mobile}")
        flash("Captcha incorrect!", "error")
        return redirect(url_for("index"))

    session.pop("captcha_signup", None)

    input_type, validated_input = validate_user_input(email_mobile)
    if not input_type:
        flash(validated_input, "error")
        return redirect(url_for("index"))

    if validated_input in users:
        flash("User already exists! Please login.", "error")
        return redirect(url_for("index"))

    otp = generate_otp()
    session['otp'] = otp
    session['otp_expiry'] = time.time() + OTP_EXPIRY_SECONDS
    session['otp_attempts'] = 0
    session['email_mobile'] = validated_input
    session['signup_mode'] = True
    session['otp_sent'] = True

    logger.info("=" * 60)
    logger.info("📝 SIGNUP OTP GENERATED")
    logger.info("=" * 60)
    logger.info(f"📧 Email: {validated_input}")
    logger.info(f"🔑 OTP: {otp}")
    logger.info(f"⏰ Expires: {OTP_EXPIRY_SECONDS // 60} minutes")
    logger.info("=" * 60)

    if input_type == 'email':
        success, msg = send_otp_email(validated_input, otp, purpose="signup")
        if success:
            flash(f"✅ OTP sent to {validated_input}. Please check your email.", "success")
        else:
            flash(f"⚠️ Could not send email. Your OTP is: {otp}", "warning")
            logger.warning(f"🔓 DEVELOPMENT OTP: {otp}")
    else:
        flash("Phone signup coming soon. Please use email.", "info")
        session.pop('otp_sent', None)
        return redirect(url_for("index"))

    return redirect(url_for("index"))


@app.route("/login", methods=["POST"])
def login():
    login_type = request.form.get("login_type")
    email_mobile = request.form.get("email_mobile", "").strip()
    captcha = request.form.get("captcha", "").strip()
    stored_captcha = session.get('captcha_login', "")

    rate_key = f"login_{request.remote_addr}"
    can_proceed, message = check_rate_limit(rate_key, max_attempts=10, window=3600)
    if not can_proceed:
        flash(message, "error")
        return redirect(url_for("index"))

    if captcha != stored_captcha:
        logger.warning(f"Login captcha failed for {email_mobile}")
        flash("Captcha incorrect!", "error")
        return redirect(url_for("index"))

    session.pop('captcha_login', None)

    input_type, validated_input = validate_user_input(email_mobile)
    if not input_type:
        flash(validated_input, "error")
        return redirect(url_for("index"))

    if validated_input not in users:
        flash("User not found! Please signup first.", "error")
        return redirect(url_for("index"))

    if login_type == "otp":
        otp = generate_otp()
        session['otp'] = otp
        session['otp_expiry'] = time.time() + OTP_EXPIRY_SECONDS
        session['otp_attempts'] = 0
        session['email_mobile'] = validated_input
        session['signup_mode'] = False
        session['otp_sent'] = True

        logger.info("=" * 60)
        logger.info("🔐 LOGIN OTP GENERATED")
        logger.info("=" * 60)
        logger.info(f"📧 Email: {validated_input}")
        logger.info(f"🔑 OTP: {otp}")
        logger.info(f"⏰ Expires: {OTP_EXPIRY_SECONDS // 60} minutes")
        logger.info("=" * 60)

        if input_type == 'email':
            success, msg = send_otp_email(validated_input, otp, purpose="login")
            if success:
                flash(f"✅ OTP sent to {validated_input}. Please check your email.", "success")
            else:
                flash(f"⚠️ Could not send email. Your OTP is: {otp}", "warning")
                logger.warning(f"🔓 DEVELOPMENT OTP: {otp}")
        else:
            flash("Phone login coming soon. Please use email.", "info")
            session.pop('otp_sent', None)
            return redirect(url_for("index"))

        return redirect(url_for("index"))

    else:  # Password login
        password = request.form.get("password", "")

        if not password:
            flash("Please enter your password", "error")
            return redirect(url_for("index"))

        if 'password' not in users[validated_input]:
            flash("Password not set. Please use OTP login.", "error")
            return redirect(url_for("index"))

        if check_password_hash(users[validated_input]['password'], password):
            session.permanent = True
            session['logged_in'] = True
            session['user'] = validated_input

            users[validated_input]['last_login'] = time.time()
            save_users(users)

            logger.info(f"✅ User {validated_input} logged in successfully")
            flash("Logged in successfully!", "success")
            return redirect(url_for("index"))
        else:
            logger.warning(f"❌ Failed login attempt for {validated_input}")
            flash("Incorrect password!", "error")
            return redirect(url_for("index"))


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    entered_otp = request.form.get("otp", "").strip()
    email_mobile = session.get("email_mobile")

    if not email_mobile:
        flash("Session expired. Please try again.", "error")
        session.pop('otp_sent', None)
        return redirect(url_for("index"))

    success, message = verify_otp_attempt(entered_otp)

    if not success:
        flash(message, "error")
        if "expired" in message.lower() or "exceeded" in message.lower():
            session.pop('otp_sent', None)
        return redirect(url_for("index"))

    if session.get('signup_mode'):
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:
            flash("Please enter both password fields", "error")
            return redirect(url_for("index"))

        if password != confirm_password:
            flash("Passwords don't match!", "error")
            return redirect(url_for("index"))

        is_valid, msg = validate_password(password)
        if not is_valid:
            flash(msg, "error")
            return redirect(url_for("index"))

        users[email_mobile] = {
            "password": generate_password_hash(password),
            "created_at": time.time(),
            "last_login": time.time()
        }
        save_users(users)
        logger.info(f"✅ New user created: {email_mobile}")
        flash("🎉 Account created successfully! Welcome to Cardwala!", "success")
    else:
        users[email_mobile]['last_login'] = time.time()
        save_users(users)
        logger.info(f"✅ User logged in: {email_mobile}")
        flash("✅ Logged in successfully!", "success")

    session.permanent = True
    session['logged_in'] = True
    session['user'] = email_mobile

    for key in ['otp', 'otp_expiry', 'otp_attempts', 'signup_mode', 'email_mobile', 'otp_sent']:
        session.pop(key, None)

    return redirect(url_for("index"))


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    email_mobile = session.get('email_mobile')
    signup_mode = session.get('signup_mode', False)

    if not email_mobile:
        return jsonify({'success': False, 'message': 'Session expired'}), 400

    otp = generate_otp()
    session['otp'] = otp
    session['otp_expiry'] = time.time() + OTP_EXPIRY_SECONDS
    session['otp_attempts'] = 0

    logger.info(f"🔄 RESEND OTP: {otp} to {email_mobile}")

    purpose = "signup" if signup_mode else "login"
    success, msg = send_otp_email(email_mobile, otp, purpose=purpose)

    if success:
        return jsonify({'success': True, 'message': 'OTP resent successfully'})
    else:
        return jsonify({'success': True, 'message': f'Development OTP: {otp}'})


@app.route("/cancel-otp", methods=["POST"])
def cancel_otp():
    for key in ['otp', 'otp_expiry', 'otp_attempts', 'signup_mode', 'email_mobile', 'otp_sent']:
        session.pop(key, None)
    return jsonify({'success': True})


@app.route("/logout")
def logout():
    user = session.get('user')
    session.clear()
    logger.info(f"👋 User {user} logged out")
    flash("Logged out successfully!", "success")
    return redirect(url_for("index"))


@app.route("/test-mail")
def test_mail():
    try:
        test_recipient = MAIL_USERNAME if MAIL_USERNAME and '@' in MAIL_USERNAME else "test@example.com"
        otp = generate_otp()

        logger.info("=" * 60)
        logger.info("📧 TESTING EMAIL CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"From: {MAIL_USERNAME}")
        logger.info(f"To: {test_recipient}")
        logger.info(f"Test OTP: {otp}")
        logger.info(f"Mail Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
        logger.info("=" * 60)

        success, message = send_otp_email(test_recipient, otp, purpose="test")

        if success:
            return f"""
            <h1 style='color: green;'>✅ Success!</h1>
            <p>Test email sent to: <strong>{test_recipient}</strong></p>
            <p>OTP: <strong>{otp}</strong></p>
            <p>Check your email inbox!</p>
            <hr>
            <a href='/'>Go Back</a>
            """
        else:
            return f"""
            <h1 style='color: red;'>❌ Email Failed</h1>
            <p>Error: {message}</p>
            <p>Development OTP: <strong>{otp}</strong></p>
            <hr>
            <h3>Check Configuration:</h3>
            <ul>
                <li>MAIL_USERNAME: {MAIL_USERNAME or 'NOT SET'}</li>
                <li>MAIL_PASSWORD: {'SET (' + str(len(MAIL_PASSWORD)) + ' chars)' if MAIL_PASSWORD else 'NOT SET'}</li>
            </ul>
            <p>Check app.log for detailed errors</p>
            <hr>
            <a href='/'>Go Back</a>
            """, 500

    except Exception as e:
        logger.error(f"Test mail exception: {e}")
        logger.exception(e)
        return f"""
        <h1 style='color: red;'>❌ Exception Occurred</h1>
        <p>{str(e)}</p>
        <p>Check app.log for full traceback</p>
        <hr>
        <a href='/'>Go Back</a>
        """, 500


@app.errorhandler(404)
def not_found(e):
    flash("Page not found", "error")
    return redirect(url_for("index"))


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    flash("An internal error occurred", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    if not os.path.exists(USERS_FILE):
        save_users({})
        logger.info("Created users.json file")

    logger.info("=" * 60)
    logger.info("🚀 CARDWALA SERVER STARTING")
    logger.info("=" * 60)
    logger.info(f"📧 MAIL_USERNAME: {MAIL_USERNAME or '❌ NOT SET'}")
    logger.info(f"🔑 MAIL_PASSWORD: {'✅ SET (' + str(len(MAIL_PASSWORD)) + ' chars)' if MAIL_PASSWORD else '❌ NOT SET'}")
    logger.info(f"📬 MAIL_SERVER: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
    logger.info("=" * 60)

    if not MAIL_USERNAME or not MAIL_PASSWORD:
        logger.warning("⚠️  EMAIL NOT CONFIGURED!")
        logger.warning("⚠️  Create a .env file with:")
        logger.warning("⚠️  MAIL_USERNAME=your-email@gmail.com")
        logger.warning("⚠️  MAIL_PASSWORD=your-app-password")
        logger.warning("⚠️  OTP will be shown in console/logs")

    app.run(debug=True, host='0.0.0.0', port=5000)