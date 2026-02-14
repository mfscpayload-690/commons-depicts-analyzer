# OAuth Setup Guide - Commons Depicts Analyzer

## 📋 What We Did

We've set up OAuth 2.0 authentication for your Commons Depicts Analyzer application. Here's what was configured:

### Files Created/Modified:

1. **`.env.example`** - Template for environment variables
2. **`setup_oauth.py`** - Interactive setup script
3. **`requirements.txt`** - Added `python-dotenv` for .env file support
4. **`backend/config.py`** - Added automatic .env file loading
5. **`README.md`** - Updated with comprehensive OAuth setup instructions

## 🚀 Quick Start Guide

### Step 1: Run the OAuth Setup Script

Open your terminal and run:

```bash
python setup_oauth.py
```

This interactive script will:
- Guide you through registering an OAuth app with Wikimedia
- Collect your Client ID and Secret
- Generate a secure Flask secret key automatically
- Create your `.env` file with all required credentials

### Step 2: Register OAuth Application

When prompted by the setup script, complete these steps:

1. Visit: https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose/oauth2

2. Fill in the registration form:
   - **Application name**: `Commons Depicts Analyzer (Development)`
   - **Application description**: `Tool for analyzing and managing depicts (P180) statements on Wikimedia Commons files`
   - **OAuth "callback" URL**: `http://localhost:5000/auth/callback`
   - **Applicable grants**: Check these boxes:
     - ✅ **Basic rights** (view basic information)
     - ✅ **Edit structured data** (required for adding depicts statements)

3. Click "Propose consumer"

4. Copy your credentials:
   - **Client ID** (looks like: `f6d7e8a9b0c1d2e3f4g5h6i7j8k9l0`)
   - **Client Secret** (looks like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8`)

### Step 3: Enter Credentials

Paste the credentials into the setup script when prompted.

### Step 4: Test OAuth

1. Start the application:
   ```bash
   python backend/main.py
   ```

2. Open http://localhost:5000 in your browser

3. Click the **"Login"** button in the top-right corner

4. You should be redirected to Wikimedia for authorization

5. Grant permissions and you'll be redirected back to your app, now logged in!

## 🔒 Security Reminders

- ✅ Your `.env` file is already in `.gitignore` (won't be committed)
- ✅ Never share your Client Secret publicly
- ✅ If credentials are exposed, regenerate them immediately at:
  https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/list

## 🛠️ Manual Setup (Alternative)

If you prefer manual configuration:

1. Create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```env
   OAUTH_CLIENT_ID=your_client_id_here
   OAUTH_CLIENT_SECRET=your_client_secret_here
   OAUTH_CALLBACK_URL=http://localhost:5000/auth/callback
   FLASK_SECRET_KEY=your_generated_secret_key_here
   ```

3. Generate a Flask secret key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

## ❓ Troubleshooting

### "OAuth is not configured" Error

**Cause**: The application can't find your OAuth credentials.

**Solution**:
1. Verify `.env` file exists in the project root
2. Check that `.env` contains `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET`
3. Restart the application after creating/editing `.env`

### "Callback URL mismatch" Error

**Cause**: The callback URL in your `.env` doesn't match the one registered with Wikimedia.

**Solution**:
1. Check your OAuth app settings at: https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/list
2. Ensure the callback URL is exactly: `http://localhost:5000/auth/callback`
3. Update either the `.env` file or the OAuth app registration to match

### Login Redirects to Error Page

**Cause**: Invalid credentials or expired authorization.

**Solution**:
1. Verify your Client ID and Secret are correct
2. Check the browser console for detailed error messages
3. Try regenerating your OAuth credentials

## 📚 What OAuth Enables

Once configured, OAuth allows users to:

- ✅ **Login** with their Wikimedia account
- ✅ **View** their username in the app
- ✅ **Add depicts statements** directly to Commons files through the UI
- ✅ **Batch edit** multiple files with suggested depicts items

**Without OAuth**, users can still:
- ✅ Analyze categories
- ✅ View statistics
- ✅ Export results
- ✅ Browse file information

## 🎯 Next Steps

1. **Run `python setup_oauth.py`** to get started
2. **Register your OAuth app** with Wikimedia
3. **Test the login flow** in your browser
4. **Start analyzing Commons categories!**

---

**Need Help?** Check the main README.md or open an issue on GitHub.
