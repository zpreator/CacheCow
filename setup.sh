#!/bin/bash

echo "🛠️  YouTube Archiver Setup Script"
echo "────────────────────────────────────────────"
echo

# ✅ Check for Docker
if ! command -v docker &> /dev/null; then
  echo "❌ Docker is not installed. Please install Docker before proceeding."
  exit 1
fi

# ✅ Check for Docker Compose
if ! command -v docker compose &> /dev/null; then
  echo "❌ Docker Compose V2 is not installed. Please install it (Docker Compose is now part of the Docker CLI)."
  exit 1
fi

# 📁 Load existing .env file if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# 📂 Ask for download path
if [ -z "$DOWNLOAD_PATH" ]; then
  read -p "📂 Enter your download path (default: $HOME/Downloads/Media): " path
  DOWNLOAD_PATH=${path:-$HOME/Downloads/Media}
else
  echo "📂 Current download path: $DOWNLOAD_PATH"
  read -p "📂 Enter your download path (leave blank to keep current: $DOWNLOAD_PATH): " path
  DOWNLOAD_PATH=${path:-$DOWNLOAD_PATH}
fi

# 📁 Create directory if missing
if [ ! -d "$DOWNLOAD_PATH" ]; then
  echo "📦 Creating directory: $DOWNLOAD_PATH"
  mkdir -p "$DOWNLOAD_PATH"
fi

# 🌐 Ask for port
read -p "🌐 Enter the port to run the app on (default: 8501): " port
PORT=${port:-8501}

# 📝 Save to .env
echo "DOWNLOAD_PATH=$DOWNLOAD_PATH" > .env
echo "PORT=$PORT" >> .env

echo
echo "✅ Configuration written to .env:"
echo "   DOWNLOAD_PATH=$DOWNLOAD_PATH"
echo "   PORT=$PORT"
echo

# 🔄 Offer to update code via git pull
read -p "⬇️  Do you want to pull the latest code from git? (y/N): " do_git_pull
if [[ "$do_git_pull" =~ ^[Yy]$ ]]; then
  echo "🔁 Running git pull..."
  git pull
fi

# 🧼 Check if container is already running
RUNNING=$(docker compose ps -q streamlit-app | xargs docker inspect -f '{{.State.Running}}' 2>/dev/null)

# 🔁 Ask to (re)start
if [ "$RUNNING" = "true" ]; then
  echo "🚨 The app is currently running."
  read -p "🔁 Do you want to restart it? (y/N): " restart
  if [[ "$restart" =~ ^[Yy]$ ]]; then
    docker compose down
    docker compose up --build -d
    echo "✅ App restarted!"
    echo "🌐 Running at: http://localhost:$PORT"
  else
    echo "👍 Leaving the current app running."
  fi
else
  read -p "🚀 Do you want to build and start the app now? (Y/n): " confirm
  if [[ "$confirm" =~ ^[Nn]$ ]]; then
    echo "👉 You can start the app later with: docker compose up --build -d"
  else
    docker compose up --build -d
    echo "✅ App is running at: http://localhost:$PORT"
  fi
fi

echo
echo "🎉 Setup complete! Happy archiving!"
