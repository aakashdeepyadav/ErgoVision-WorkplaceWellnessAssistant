#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Creating Python virtual environment (.venv)..."
  if command -v python3.12 >/dev/null 2>&1; then
    echo "Using Python 3.12 for MediaPipe compatibility."
    python3.12 -m venv .venv
  elif command -v python3.11 >/dev/null 2>&1; then
    echo "Using Python 3.11 for MediaPipe compatibility."
    python3.11 -m venv .venv
  else
    echo "Python 3.12/3.11 not found; using python3 fallback."
    python3 -m venv .venv
  fi
fi

source .venv/bin/activate

echo "Installing backend dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Installing frontend dependencies..."
(
  cd frontend
  npm install
)

if [[ -f ".env.example" && ! -f ".env" ]]; then
  cp .env.example .env
fi

if [[ -f "frontend/.env.example" && ! -f "frontend/.env" ]]; then
  cp frontend/.env.example frontend/.env
fi

mkdir -p data

echo "Setup complete."
echo "Backend: .venv/bin/python server.py"
echo "Frontend: cd frontend && npm run dev"
