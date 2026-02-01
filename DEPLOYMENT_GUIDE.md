# Omar Agent - Step-by-Step Deployment & Execution Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Configuration](#configuration)
4. [Running the Agent](#running-the-agent)
5. [Testing the Agent](#testing-the-agent)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **Python 3.9+** - Download from [python.org](https://www.python.org/downloads/)
- **Git** - Download from [git-scm.com](https://git-scm.com/)
- **Docker** (Optional, for containerized deployment) - Download from [docker.com](https://www.docker.com/)

### Required Accounts/Services
- **Odoo Account** - Your Three Lines Odoo instance (already set up)
- **AI API Access** - Custom AI endpoint at ai3lines.com (already set up)
- **GitHub Account** - To clone the repository

---

## Local Development Setup

### Step 1: Clone the Repository

```bash
# Open terminal/command prompt and navigate to your workspace
cd C:\Users\abdularafay\Videos

# Clone the repository
git clone https://github.com/3LGroup/omar-ai-agent.git

# Navigate into the project directory
cd omar-ai-agent
```

### Step 2: Create Virtual Environment

**Windows:**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate
```

**Linux/Mac:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all required packages
pip install -r requirements.txt
```

This will install:
- FastAPI (web framework)
- OpenAI SDK (for AI integration)
- xmlrpc (for Odoo connection)
- And all other dependencies

---

## Configuration

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root directory:

```bash
# Copy the example file
copy .env.example .env
```

Edit the `.env` file with your credentials:

```env
# AI Configuration
OPENAI_API_KEY=VSB0H0H-S6G43J4-QRA7JZA-SJ0K7A8
OPENAI_BASE_URL=https://ai3lines.com/api/v1/openai
OPENAI_MODEL=localmodel
USE_FUNCTION_CALLING=true

# Odoo ERP Configuration
ODOO_URL=https://three-lines-stage5-27653523.dev.odoo.com
ODOO_DB=three-lines-stage5-27653523
ODOO_USERNAME=abdulrafay@3lines.com.sa
ODOO_API_KEY=1c694ec83d509cb5488df484a1fbc16e78c8dfc8

# Application Settings
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=development

# Optional: Stripe (only if using payment features)
STRIPE_API_KEY=your_stripe_key_here

# Optional: Nookal (legacy, not needed for Three Lines)
NOOKAL_API_KEY=
```

**Security Note:** The `.env` file is already in `.gitignore` and will NOT be committed to GitHub.

---

## Running the Agent

### Step 5: Start the Server

**Option A: Direct Python (Recommended for Development)**

```bash
# Make sure virtual environment is activated
# You should see (venv) in your prompt

# Run the FastAPI server
python app.py
```

You should see output like:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Option B: Using Uvicorn Directly**

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag automatically restarts the server when code changes.

**Option C: Using Docker**

```bash
# Build the Docker image
docker build -t omar-agent .

# Run the container
docker run -p 8000:8000 --env-file .env omar-agent
```

### Step 6: Verify Server is Running

Open your browser and navigate to:
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/threelines/health

You should see the Swagger UI with all available endpoints.

---

## Testing the Agent

### Step 7: Test Basic Functionality

#### Test 1: Health Check

```bash
curl http://localhost:8000/threelines/health
```

Expected response:
```json
{
  "status": "healthy",
  "message": "Three Lines Operations Agent is running",
  "odoo_connected": true
}
```

#### Test 2: Product Search via API

**Using curl:**
```bash
curl -X POST http://localhost:8000/threelines/products/search \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"brake\"}"
```

**Using PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/threelines/products/search" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query": "brake"}'
```

Expected response:
```json
{
  "success": true,
  "products": [
    {
      "id": 123,
      "name": "F-15 Brake Assembly",
      "part_number": "ABC-123",
      "quantity_on_hand": 10
    }
  ]
}
```

#### Test 3: Chat with Omar

**Using curl:**
```bash
curl -X POST http://localhost:8000/threelines/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hello Omar, do we have any F-15 parts in stock?\"}"
```

**Using Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/threelines/chat",
    json={"message": "Hello Omar, do we have any F-15 parts in stock?"}
)

print(response.json())
```

### Step 8: Test All Functions

Create a test script `test_omar.py`:

```python
import requests

BASE_URL = "http://localhost:8000"

def test_product_search():
    """Test searching for products"""
    response = requests.post(
        f"{BASE_URL}/threelines/products/search",
        json={"query": "brake"}
    )
    print("Product Search:", response.json())

def test_stock_check():
    """Test checking stock availability"""
    response = requests.post(
        f"{BASE_URL}/threelines/stock/check",
        json={"part_number": "ABC-123"}
    )
    print("Stock Check:", response.json())

def test_order_status():
    """Test getting order status"""
    response = requests.get(
        f"{BASE_URL}/threelines/orders/SO-001"
    )
    print("Order Status:", response.json())

def test_chat():
    """Test chat interface"""
    response = requests.post(
        f"{BASE_URL}/threelines/chat",
        json={"message": "What products do we have?"}
    )
    print("Chat Response:", response.json())

if __name__ == "__main__":
    print("Testing Omar Agent...\n")
    test_product_search()
    print("\n" + "="*50 + "\n")
    test_stock_check()
    print("\n" + "="*50 + "\n")
    test_order_status()
    print("\n" + "="*50 + "\n")
    test_chat()
```

Run tests:
```bash
python test_omar.py
```

---

## Production Deployment

### Step 9: Choose Deployment Platform

#### Option A: Deploy to Cloud Server (AWS/DigitalOcean/Azure)

**1. Set up a Linux server (Ubuntu 22.04 recommended)**

SSH into your server:
```bash
ssh user@your-server-ip
```

**2. Install dependencies:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.9+
sudo apt install python3 python3-pip python3-venv -y

# Install Git
sudo apt install git -y
```

**3. Clone and setup:**
```bash
# Clone repository
git clone https://github.com/3LGroup/omar-ai-agent.git
cd omar-ai-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
nano .env
# Paste your credentials and save (Ctrl+X, Y, Enter)
```

**4. Run with systemd (auto-restart on crash):**

Create service file:
```bash
sudo nano /etc/systemd/system/omar.service
```

Paste this content:
```ini
[Unit]
Description=Omar AI Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/omar-ai-agent
Environment="PATH=/home/your-username/omar-ai-agent/venv/bin"
ExecStart=/home/your-username/omar-ai-agent/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable omar
sudo systemctl start omar
sudo systemctl status omar
```

**5. Set up Nginx as reverse proxy:**

```bash
sudo apt install nginx -y

sudo nano /etc/nginx/sites-available/omar
```

Paste:
```nginx
server {
    listen 80;
    server_name omar.3lines.com.sa;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/omar /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### Option B: Deploy with Docker

**1. Build and run:**
```bash
# On your server
git clone https://github.com/3LGroup/omar-ai-agent.git
cd omar-ai-agent

# Create .env file with your credentials
nano .env

# Build image
docker build -t omar-agent .

# Run container
docker run -d \
  --name omar \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  omar-agent

# View logs
docker logs -f omar
```

#### Option C: Deploy to Heroku

```bash
# Install Heroku CLI
# Visit: https://devcenter.heroku.com/articles/heroku-cli

# Login
heroku login

# Create app
heroku create omar-3lines

# Set environment variables
heroku config:set OPENAI_API_KEY=VSB0H0H-S6G43J4-QRA7JZA-SJ0K7A8
heroku config:set OPENAI_BASE_URL=https://ai3lines.com/api/v1/openai
heroku config:set ODOO_URL=https://three-lines-stage5-27653523.dev.odoo.com
# ... set all other variables

# Deploy
git push heroku main

# Open app
heroku open
```

### Step 10: Set Up SSL Certificate (Production)

**Using Let's Encrypt (Free):**

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d omar.3lines.com.sa

# Auto-renewal is configured automatically
```

### Step 11: Set Up Monitoring

**Option A: Simple Log Monitoring**

```bash
# View live logs
tail -f /var/log/syslog | grep omar

# Or with Docker
docker logs -f omar
```

**Option B: Use PM2 (Process Manager)**

```bash
# Install PM2
npm install -g pm2

# Start Omar with PM2
pm2 start app.py --name omar --interpreter python3

# Save PM2 configuration
pm2 save

# Setup auto-start on server reboot
pm2 startup

# Monitor
pm2 monit
```

---

## Usage Examples

### Example 1: Web Chat Integration

Create a simple HTML page to chat with Omar:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Omar - Three Lines Assistant</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; }
        #chat { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; }
        input { width: 80%; padding: 10px; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h1>Omar - Three Lines Operations Assistant</h1>
    <div id="chat"></div>
    <input id="message" placeholder="Ask Omar anything...">
    <button onclick="sendMessage()">Send</button>

    <script>
        async function sendMessage() {
            const message = document.getElementById('message').value;
            const chat = document.getElementById('chat');

            chat.innerHTML += `<p><strong>You:</strong> ${message}</p>`;

            const response = await fetch('http://localhost:8000/threelines/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message})
            });

            const data = await response.json();
            chat.innerHTML += `<p><strong>Omar:</strong> ${data.response}</p>`;
            chat.scrollTop = chat.scrollHeight;

            document.getElementById('message').value = '';
        }
    </script>
</body>
</html>
```

Save as `chat.html` and open in browser.

### Example 2: WhatsApp Integration (Future)

When ready, you can integrate with WhatsApp Business API to allow employees to message Omar.

---

## Troubleshooting

### Problem: Server won't start

**Solution:**
```bash
# Check if port 8000 is already in use
# Windows:
netstat -ano | findstr :8000

# Linux:
lsof -i :8000

# Kill the process or use a different port
python app.py --port 8001
```

### Problem: Odoo connection fails

**Solution:**
```bash
# Test Odoo credentials manually
python -c "
import xmlrpc.client
common = xmlrpc.client.ServerProxy('https://three-lines-stage5-27653523.dev.odoo.com/xmlrpc/2/common')
uid = common.authenticate('three-lines-stage5-27653523', 'abdulrafay@3lines.com.sa', '1c694ec83d509cb5488df484a1fbc16e78c8dfc8', {})
print(f'Connected! User ID: {uid}')
"
```

### Problem: AI API not responding

**Solution:**
```bash
# Test AI endpoint
curl -X POST https://ai3lines.com/api/v1/openai/chat/completions \
  -H "Authorization: Bearer VSB0H0H-S6G43J4-QRA7JZA-SJ0K7A8" \
  -H "Content-Type: application/json" \
  -d '{"model":"localmodel","messages":[{"role":"user","content":"Hello"}]}'
```

### Problem: Module import errors

**Solution:**
```bash
# Reinstall dependencies
pip install --upgrade --force-reinstall -r requirements.txt

# Check Python version (must be 3.9+)
python --version
```

---

## Next Steps

### Immediate (Week 1)
1. ✅ **Test locally** - Run through all test examples above
2. ✅ **Verify Odoo connection** - Ensure all 13 functions work
3. ✅ **Deploy to staging server** - Test in production-like environment

### Short-term (Weeks 2-4)
4. **Build web interface** - Simple chat UI for employees
5. **Add authentication** - User login system
6. **Train employees** - Show 5-10 employees how to use Omar
7. **Gather feedback** - Improve based on real usage

### Medium-term (Months 2-3)
8. **Implement Supabase** - Replace Firebase with Supabase
9. **Add document search** - RAG for manuals/specs
10. **WhatsApp integration** - For field staff
11. **Analytics dashboard** - Monitor usage and performance

---

## Quick Reference

### Start Server
```bash
cd omar-ai-agent
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
python app.py
```

### Stop Server
Press `Ctrl+C` in the terminal

### View Logs
```bash
tail -f logs/app.log
```

### Update Code
```bash
git pull origin main
pip install -r requirements.txt
# Restart server
```

### API Endpoints
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/threelines/health
- Chat: http://localhost:8000/threelines/chat
- Search: http://localhost:8000/threelines/products/search

---

## Support

**Technical Issues:**
- Check logs in `logs/` directory
- Review [THREE_LINES_AGENT_PLAN.md](THREE_LINES_AGENT_PLAN.md)
- GitHub Issues: https://github.com/3LGroup/omar-ai-agent/issues

**Contact:**
- Email: abdulrafay@3lines.com.sa
- Project: Three Lines Operations Agent "Omar"

---

**Last Updated:** January 26, 2026
**Version:** 1.0.0
