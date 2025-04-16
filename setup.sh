#!/bin/bash

echo "🐋 Setting up HuggingWhale.AI environment..."

# Step 1: Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Step 2: Upgrade pip and install requirements
pip install --upgrade pip

echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Step 3: Reminder to set env variables
echo ""
echo "✅ Setup complete!"
echo "⚠️  Don’t forget to create a .env file with your API keys:"
echo "    OPENAI_API_KEY=your-openai-key"
echo "    VOYAGE_API_KEY=your-voyage-key"
echo ""
echo "👉 To start using HuggingWhale.AI:"
echo "   source venv/bin/activate"
echo "   python app.py"
