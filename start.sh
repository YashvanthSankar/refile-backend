#!/bin/bash

# Quick start script for refile backend

echo "🚀 Starting refile backend setup..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "📝 Copy .env.example to .env and fill in your Supabase credentials:"
    echo "   cp .env.example .env"
    echo "   nano .env  # or use your favorite editor"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create upload directory
mkdir -p user_uploads

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Run the database schema in Supabase (see schema.sql)"
echo "   2. Start the server:"
echo "      uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "   3. Test the API (see API_EXAMPLES.md)"
echo ""
echo "🌐 Server will be available at: http://localhost:8000"
echo "📚 API docs at: http://localhost:8000/docs"
