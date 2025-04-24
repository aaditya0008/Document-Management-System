import hashlib
import random
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import jwt
import smtplib
from sqlalchemy.orm import Session
from helpers.database import get_db  # Import get_db from the appropriate module
from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from helpers.constants import SECRET_KEY, ALGORITHM, SENDER_EMAIL, APP_PASSWORD
from sqlalchemy.sql import text  # Import text for raw SQL queries

# Logging Setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Hash Password
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Verify Password
def verify_password(password: str, hashed_password: str) -> bool:
    return hash_password(password) == hashed_password

# Generate JWT Token
def generate_jwt_token(email: str, role: str):
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# Send OTP Email
def send_otp_email(email: str, otp: str):
    print(otp)
    """
    Sends an OTP email to the provided recipient email.

    :param email: Recipient email address.
    :param otp: The OTP code to be sent.
    """
    subject = "OTP for Verification"
    body = f"Your OTP for verification is: {otp}"

    # Create email message
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # Create SMTP connection
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()  # Identify with the server
            server.starttls()  # Secure connection
            server.login(SENDER_EMAIL, APP_PASSWORD)  # Login with App Password

            # Send email
            server.sendmail(SENDER_EMAIL, email, msg.as_string())

        print(f"📧 OTP email sent to {email}")

    except Exception as e:
        print(f"❌ Error sending OTP email: {e}")

# User Registration
def register_user(db: Session, email: str):
    email = email.strip().lower()

    # Check if OTP already exists for this email
    existing_otp = db.execute(
        text("SELECT * FROM otp_verification WHERE email = :email"),
        {"email": email}
    ).fetchone()

    if existing_otp:
        raise HTTPException(status_code=400, detail="OTP already sent. Please verify.")

    otp = str(random.randint(100000, 999999))

    # Store OTP in otp_verification table
    db.execute(
        text("INSERT INTO otp_verification (email, otp, verified) VALUES (:email, :otp, :verified)"),
        {"email": email, "otp": otp, "verified": False}
    )
    db.commit()

    send_otp_email(email, otp)

    return {"message": "OTP sent successfully"}


# Verify OTP
def verify_otp(db: Session, email: str, otp: str, username: str, password: str, role: str):
    email = email.strip().lower()
    otp = otp.strip()

    # Check if OTP exists and is valid
    otp_entry = db.execute(
        text("SELECT * FROM otp_verification WHERE email = :email"),
        {"email": email}
    ).fetchone()

    if not otp_entry or otp_entry[2] != otp:  # Assuming OTP is in the 3rd column
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Mark OTP as verified
    db.execute(
        text("UPDATE otp_verification SET verified = TRUE WHERE email = :email"),
        {"email": email}
    )

    hashed_password = hash_password(password)

    # Store user credentials in users table
    db.execute(
        text("INSERT INTO users (username, email, password, role) VALUES (:username, :email, :password, :role)"),
        {"username": username, "email": email, "password": hashed_password, "role": role}
    )

    db.commit()

    return {"message": "Account verified and registered successfully"}


# User Login
def login_user(db: Session, email: str, password: str):
    email = email.strip().lower()

    # Use text() for raw SQL queries
    user = db.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email}).fetchone()
    user_otp_veri=db.execute(text("SELECT * FROM otp_verification WHERE email = :email"), {"email": email}).fetchone()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # Access the tuple by index (adjust indices based on your table schema)
  # Access the tuple by index (adjust indices based on your table schema)
    user_password = user[3]  # 'password' is the 4th column in the 'users' table
    user_verified = user_otp_veri[3]  #  'verified' is the 7th column in the 'users' table
    user_role = user[4]      #  'role' is the 5th column in the 'users' table



    if not verify_password(password, user_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    if not user_verified:
        raise HTTPException(status_code=400, detail="User not verified. Please verify your account.")

    token = generate_jwt_token(email, user_role)
    return {"access_token": token, "token_type": "bearer"}

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")  # Extract the email (subject) from the token
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token: Email not found")

        # Fetch the user from the database using the email
        user = db.execute(
            text("SELECT id, username, email, role FROM users WHERE email = :email"),
            {"email": email}
        ).mappings().fetchone()  # Use .mappings() to return a dictionary-like result

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Return the user details as a dictionary
        return {"id": user["id"], "username": user["username"], "email": user["email"], "role": user["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")