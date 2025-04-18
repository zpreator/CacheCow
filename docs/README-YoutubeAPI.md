# 🔐 YouTube API Setup (First-Time Only)

This will use the google API to fetch your current list of subscriptions saving you time.

## ✨ Step 1: Create a Google Cloud Project

1. Visit the Google Cloud Console

2. Click the project dropdown (top left) → New Project

3. Name it something like YouTubeDownloader and click Create

## 📦 Step 2: Enable the YouTube API

1. Open the project

2. Go to APIs & Services → Library

3. Search for YouTube Data API v3

4. Click it → Click Enable

## 🧪 Step 3: Configure OAuth Consent Screen

1. Go to APIs & Services → OAuth consent screen

2. Choose External, then click Create

3. Fill in:

    - App name: Anything you like

    - User support email: Your email

    - Developer contact info: Your email

4. Click Save and Continue through the rest

5. Under Test Users, add your Google account email

## 🔑 Step 4: Create OAuth Credentials

1. Go to APIs & Services → Credentials

2. Click + CREATE CREDENTIALS → OAuth client ID

3. Choose Desktop App

4. Name it something like YouTubeTokenApp

5. Click Create, then Download JSON