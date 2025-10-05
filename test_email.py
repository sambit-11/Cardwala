#!/usr/bin/env python3
"""
Simple Email Configuration Test Script
Run this to verify your Gmail setup before using the app
"""

import os
from dotenv import load_dotenv

print("=" * 60)
print("🧪 EMAIL CONFIGURATION TEST")
print("=" * 60)

# Load .env file
load_dotenv()

MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

# Check configuration
print("\n1. Checking .env file...")
if not os.path.exists('.env'):
    print("   ❌ .env file not found!")
    print("   Create .env file with:")
    print("   MAIL_USERNAME=your-email@gmail.com")
    print("   MAIL_PASSWORD=your-app-password")
    exit(1)
else:
    print("   ✅ .env file exists")

print("\n2. Checking MAIL_USERNAME...")
if not MAIL_USERNAME or MAIL_USERNAME == 'your-email@gmail.com':
    print("   ❌ MAIL_USERNAME not configured!")
    print(f"   Current value: {MAIL_USERNAME}")
    print("   Please edit .env and add your Gmail address")
    exit(1)
else:
    print(f"   ✅ MAIL_USERNAME: {MAIL_USERNAME}")

print("\n3. Checking MAIL_PASSWORD...")
if not MAIL_PASSWORD or MAIL_PASSWORD == 'your-16-char-app-password':
    print("   ❌ MAIL_PASSWORD not configured!")
    print("   Please edit .env and add your Gmail App Password")
    print("   Get it from: https://myaccount.google.com/apppasswords")
    exit(1)
else:
    print(f"   ✅ MAIL_PASSWORD: {'*' * len(MAIL_PASSWORD)} ({len(MAIL_PASSWORD)} chars)")

print("\n4. Validating email format...")
if '@' not in MAIL_USERNAME or '.' not in MAIL_USERNAME:
    print("   ❌ Invalid email format!")
    exit(1)
else:
    print("   ✅ Email format looks good")

print("\n5. Testing SMTP connection...")
try:
    import smtplib
    from email.mime.text import MIMEText
    
    # Try to connect
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    
    # Try to send test email
    msg = MIMEText('This is a test email from Cardwala setup script.')
    msg['Subject'] = 'Cardwala Test Email'
    msg['From'] = MAIL_USERNAME
    msg['To'] = MAIL_USERNAME
    
    server.send_message(msg)
    server.quit()
    
    print("   ✅ SMTP connection successful!")
    print(f"   ✅ Test email sent to {MAIL_USERNAME}")
    
except smtplib.SMTPAuthenticationError:
    print("   ❌ SMTP Authentication Failed!")
    print("   Possible issues:")
    print("   - Using regular password instead of App Password")
    print("   - App Password is incorrect")
    print("   - 2-Step Verification not enabled")
    print("\n   Steps to fix:")
    print("   1. Enable 2-Step Verification at: https://myaccount.google.com/security")
    print("   2. Generate App Password at: https://myaccount.google.com/apppasswords")
    print("   3. Copy the 16-char password (remove spaces)")
    print("   4. Update MAIL_PASSWORD in .env file")
    exit(1)
    
except Exception as e:
    print(f"   ❌ Connection failed: {str(e)}")
    exit(1)

print("\n" + "=" * 60)
print("✅ ALL CHECKS PASSED!")
print("=" * 60)
print("\nYour email configuration is correct!")
print("You can now run the app and receive OTPs via email.")
print("\nNext steps:")
print("1. Run: python app.py")
print("2. Visit: http://localhost:5000")
print("3. Use EMAIL (not phone) for signup")
print("4. Check your email for OTP")
print("\n🎉 Happy coding!")
print("=" * 60)
