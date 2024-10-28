from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import streamlit as st
import os
import json

# Path to your OAuth 2.0 credentials
CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
CONFIG_FILE = "/app/shared_media/Media/YouTube/config.json"

# Function to authenticate and get YouTube subscriptions
def authenticate_youtube():
    creds = None

    # Check if the token.json file exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                return creds
            except:
                pass
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        flow.redirect_uri = 'http://localhost:8080'  # Redirect URI for your app
        auth_url, _ = flow.authorization_url(prompt='consent')

        # Display the URL for the user to visit
        st.write(f'Please go to this URL: [Authorize Here]({auth_url})')

        # Create a text input for the authorization code
        code = st.text_input('Enter the authorization code:')
        if code:
            if "http" in code:
                # http://localhost:8080/?state=oqwylM1WDiHD5gYXBLiFK0Bzp2s6sO&code=4/0AVG7fiTvJQKPlR6fOOo38xeBL3ZrEUg0qOrDAujqYSxgBd7SPXqztMZ4GpSfH8946IWqOw&scope=https://www.googleapis.com/auth/youtube.readonly
                code = code.split("code=")[1].split("&scope")[0]
            flow.fetch_token(code=code)
            creds = flow.credentials

            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

            st.success('Authentication successful!')

    return creds

# Function to get YouTube subscriptions
def get_subscriptions(creds):
    youtube = build('youtube', 'v3', credentials=creds)

    subscriptions = []
    request = youtube.subscriptions().list(
        part='snippet',
        mine=True,
        maxResults=50  # Fetch up to 50 subscriptions per request
    )

    while request is not None:
        response = request.execute()
        subscriptions.extend(response.get('items', []))
        request = youtube.subscriptions().list_next(request, response)

    return subscriptions

# Function to load config file
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    empty_config = {
        "youtube": {},
    }
    return empty_config

# Function to save config file
def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Merge the fetched subscriptions with the current config
def refresh_data(config, creds):
    updated_config = {
        "youtube": {},
    }

    subscriptions = get_subscriptions(creds)

    # Keep existing settings for old subscriptions, add new ones as False
    for sub in subscriptions:
        title = sub["snippet"]["title"]
        channel_id = sub["snippet"]["resourceId"]["channelId"]
        channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
        thumbnail_url = sub["snippet"]["thumbnails"]["default"]["url"]
        default_selected = False
        default_tag = "other"
        if title in config["youtube"].keys():
            default_selected = config["youtube"][title]["subscribe"]
            default_tag = config["youtube"][title]["tag"]
        updated_config["youtube"][title] = {
            "subscribe": default_selected,
            "tag": default_tag,
            "link": channel_url,
            "image": thumbnail_url  
        }

    # Add ToDownload playlist as option
    subscribed = False
    if "ToDownload" in config["youtube"].keys():
        subscribed = config["youtube"]["ToDownload"].get("subscribe", False)
    updated_config["youtube"]["ToDownload"] = {
        "subscribe": subscribed,
        "tag": "other",
        "link": "https://www.youtube.com/playlist?list=PLXRlnUdzf9f1KbIDcNiTRVLgsQQSiuDnL",
        "image": "https://yt3.ggpht.com/yti/ANjgQV-B-hb25HReQCi5kpbamwS0XHwOuaBV-SKG3TmBxrXIW5RQ=s108-c-k-c0x00ffffff-no-rj"
    }

    save_config(updated_config)
    return updated_config


def streamlit_app():
    if "creds" not in st.session_state:
        st.session_state.creds = None
    
    if not st.session_state.creds:
        st.session_state.creds = authenticate_youtube()
        st.rerun()
    else:
        # Load existing config (if any)
        config = load_config()

        

        # Streamlit app layout
        st.title("Media Manager")

        if st.button("Fetch Data"):
            config = refresh_data(config, st.session_state.creds)

        data = {
            "youtube": {},
        }
        st.subheader("Youtube Subscriptions")
        num_columns = 5
        # Separate the subscriptions into checked and unchecked
        checked_subscriptions = [title for title in config["youtube"].keys() if config["youtube"][title]["subscribe"]]
        unchecked_subscriptions = [title for title in config["youtube"].keys() if not config["youtube"][title]["subscribe"]]
        rows = [i for i in range(0, len(checked_subscriptions), num_columns)]
        for row in rows:
            cols = st.columns(num_columns)
            for i, col in enumerate(cols):
                if row + i < len(checked_subscriptions):
                    with col:
                        title = checked_subscriptions[row + i]
                        # for title in sorted(checked_subscriptions, key=str.casefold):
                        selected = config["youtube"][title]["subscribe"]
                        tag = config["youtube"][title]["tag"]
                        link = config["youtube"][title]["link"]
                        image = config["youtube"][title].get("image")
                        if image:
                            st.image(image)
                        data["youtube"][title] = {
                            "subscribe": st.checkbox(title, value=selected),
                            "tag": st.text_input("Category", value=tag, key=f"tag{title}"),
                            "link": link,
                            "image": image
                        }
        with st.expander("Not Checked"):
            for title in sorted(unchecked_subscriptions, key=str.casefold):
                selected = config["youtube"][title]["subscribe"]
                tag = config["youtube"][title]["tag"]
                link = config["youtube"][title]["link"]
                image = config["youtube"][title].get("image")
                data["youtube"][title] = {
                    "subscribe": st.checkbox(title, value=selected),
                    "tag": st.text_input("Category", value=tag, key=f"tag{title}"),
                    "link": link,
                    "image": image
                }

        # Save button to write the changes to the config file
        if st.button("Save"):
            save_config(data)
            st.success("Configurations saved!")
            st.rerun()


if __name__ == '__main__':
    # Start the Streamlit app
    streamlit_app()