#!/bin/bash

echo "=========================================="
echo " CRABEX - Google OAuth & Forgot Password"
echo " Installation Script for Linux/Mac"
echo "=========================================="
echo ""

echo "[1/5] Installing required Python packages..."
pip3 install Flask-Mail authlib python-dotenv requests
echo ""

echo "[2/5] Updating database schema..."
python3 database.py
echo ""

echo "[3/5] Creating .env template file..."
cat > .env.template << 'EOF'
# Email Configuration for Forgot Password
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-google-client-secret
EOF
echo ".env.template created! Copy to .env and fill in your credentials."
echo ""

echo "[4/5] Creating .gitignore to protect sensitive files..."
cat > .gitignore << 'EOF'
# Environment variables
.env

# Database
*.db

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/

# IDE
.vscode/
.idea/
EOF
echo ".gitignore created!"
echo ""

echo "[5/5] Setup Instructions:"
echo "=========================================="
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Set up Gmail App Password:"
echo "   - Go to: https://myaccount.google.com/apppasswords"
echo "   - Generate app password for 'Mail'"
echo ""
echo "2. Set up Google OAuth:"
echo "   - Go to: https://console.cloud.google.com/"
echo "   - Create project and OAuth credentials"
echo "   - Add redirect URI: http://localhost:5000/login/google/authorized"
echo ""
echo "3. Configure environment variables:"
echo "   - Copy .env.template to .env"
echo "   - Fill in your Gmail and Google OAuth credentials"
echo "   $ cp .env.template .env"
echo "   $ nano .env  # or use your preferred editor"
echo ""
echo "4. Run the application:"
echo "   $ python3 app.py"
echo ""
echo "5. Test features:"
echo "   - Forgot Password: http://localhost:5000/forgot-password"
echo "   - Google Sign-In: http://localhost:5000/login"
echo ""
echo "For detailed instructions, see: QUICK_START.md"
echo "=========================================="
echo ""
