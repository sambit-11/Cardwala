# 📧 Cardwala Setup Instructions

## Issue 1: OTP Not Arriving - SOLUTION ✅

### Why OTP isn't coming:
1. **Email not configured** - You need to setup Gmail App Password in `.env` file
2. **Mobile OTP not supported yet** - Currently only email OTP works

### ✨ Quick Fix for Email OTP:

#### Step 1: Edit the `.env` file
Open the `.env` file in the workspace and replace these lines:
```env
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
```

With your actual Gmail credentials:
```env
MAIL_USERNAME=youractualemail@gmail.com
MAIL_PASSWORD=abcdefghijklmnop
```

#### Step 2: Get Gmail App Password
1. Go to: https://myaccount.google.com/apppasswords
2. You'll need **2-Step Verification** enabled first
3. Click "Generate" for Mail app
4. Copy the 16-character password (it looks like: `abcd efgh ijkl mnop`)
5. Remove spaces and paste into `.env` file

#### Step 3: Save and Restart
```bash
# Save the .env file, then restart the app
python app.py
```

## Issue 2: OTP Form on Same Page - FIXED ✅

The templates have been updated so that:
- ✅ OTP input appears **inline** in the same login/signup box
- ✅ No page redirects
- ✅ Smooth animations
- ✅ Clear visual feedback

## 📱 About Mobile OTP

**Current Status**: Mobile OTP via SMS is not implemented yet.

**What works**: 
- ✅ Email OTP (once configured)
- ✅ Email validation
- ✅ Mobile number input (accepted but will show "coming soon" message)

**What doesn't work**:
- ❌ SMS OTP sending (requires Twilio/similar service)

### To Use the App Now:
👉 **Use EMAIL instead of mobile number for signup/login**

Example:
- ✅ Use: `john@gmail.com`
- ❌ Don't use: `+1234567890` (will show "Phone signup coming soon")

## 🎯 Complete Setup Checklist

- [ ] Edit `.env` file with your Gmail address
- [ ] Get Gmail App Password from Google
- [ ] Add App Password to `.env` file
- [ ] Save the file
- [ ] Restart the app: `python app.py`
- [ ] Open browser: `http://localhost:5000`
- [ ] Test with email signup (not phone number)
- [ ] Check your Gmail inbox for OTP

## 🧪 Testing

### Test 1: Check Email Configuration
```bash
# Run the app and visit this URL:
http://localhost:5000/test-mail
```

If successful, you'll receive a test email!

### Test 2: Signup Flow
1. Go to `http://localhost:5000`
2. Click "✨ Sign Up" tab
3. Enter your **EMAIL** (not phone)
4. Enter captcha
5. Click "Sign Up"
6. **OTP form appears on same page** ✅
7. Check your email inbox
8. Enter OTP
9. Create password
10. Done!

## 🔍 Finding Your OTP

### If email is configured correctly:
✅ Check Gmail inbox - OTP arrives in 2-5 seconds

### If email fails:
The app shows OTP in multiple places:

#### 1. Orange Warning Message (On Webpage)
```
⚠️ Could not send email. Your OTP is: 123456
```

#### 2. Terminal Output
```
====================================
📝 SIGNUP OTP GENERATED
====================================
📧 Email: user@example.com
🔑 OTP: 123456
⏰ Expires: 10 minutes
====================================
```

#### 3. Log File
```bash
tail -20 app.log | grep OTP
```

## ❌ Common Errors & Solutions

### Error: "Email not configured"
**Solution**: Edit `.env` file and add your Gmail credentials

### Error: "Email authentication failed"
**Solution**: 
- Make sure you're using **App Password**, NOT regular Gmail password
- App Password is 16 characters long
- Get it from: https://myaccount.google.com/apppasswords

### Error: "Invalid email format"
**Solution**: Use proper email format like `name@gmail.com`

### Error: "Phone signup coming soon"
**Solution**: Use email instead of phone number for now

### Error: "Templates not found"
**Solution**: The templates are now created! Just restart the app.

## 📋 Current Features

### ✅ Working:
- Email signup/login
- OTP via email (when configured)
- OTP form inline on same page
- Password login
- Captcha verification
- Rate limiting
- User session management

### ⏳ Coming Soon:
- SMS OTP for mobile numbers
- Social login (Google, Facebook)
- Password recovery
- Email verification links

## 🎉 You're All Set!

Once you configure Gmail credentials in `.env`, everything will work perfectly!

**Start here:**
1. Edit `.env` with your Gmail
2. Run `python app.py`
3. Visit `http://localhost:5000`
4. Use **EMAIL** for signup (not phone)
5. Get OTP in your email
6. Enjoy! 🚀
