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
CONFIG_FILE = "data/config.json"

# Function to authenticate and get YouTube subscriptions
def authenticate_youtube(show_link=True):
    creds = None

    # Check if the token.json file exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, try auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                return creds
            except Exception as e:
                st.warning(f"Error refreshing token: {e}")

        # Check if client_secret.json exists before trying to use it
        if not os.path.exists(CLIENT_SECRETS_FILE):
            st.error(
                f"Missing {CLIENT_SECRETS_FILE}. Please follow the instructions "
                "to download your credentials from the Google Developer Console."
            )
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            flow.redirect_uri = 'http://localhost:8501'
            auth_url, _ = flow.authorization_url(prompt='consent')

            if show_link:
                st.write(f'Please go to this URL: [Authorize Here]({auth_url})')
            query_params = st.query_params
            code = query_params.get("code")

            if code:
                if "http" in code:
                    # Extract code from redirect URL
                    code = code.split("code=")[1].split("&")[0]

                flow.fetch_token(code=code)
                creds = flow.credentials

                # Save the credentials
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())

                st.success('Authentication successful!')
        except Exception as e:
            st.error(f"OAuth flow failed: {e}")
            return None

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
        "tags": ["other"],
        "settings": {}
    }
    return empty_config

# Function to save config file
def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Merge the fetched youtube subscriptions with the current config
def refresh_data(config, creds):
    updated_config = {
        "youtube": {},
        "tags": config["tags"],
        "settings": config["settings"]
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

def save_channel_config(config, title, url, tag, image, sub):
    if not title:
        st.error("Please provide a Channel Name")
        return
    if not url:
        st.error("Please provide a valid youtube URL. Hint, navigate to the channel, click 'videos' and copy the URL in the address bar")
        return
    if not image:
        image = "https://randomuser.me/api/portraits/men/52.jpg"
    config["youtube"][title] = {
        "subscribe": sub,
        "tag": tag,
        "link": url,
        "image": image
    }
    save_config(config)

def youtube_page():
    st.title("YouTube Subscriptions")
    config = load_config()

    cols = st.columns(2)
    with cols[0]:
        save_btn = st.button("Save Changes")
    with cols[1]:
        if st.button("Fetch YouTube Data"):
            st.session_state.creds = authenticate_youtube()
            if st.session_state.creds:
                config = refresh_data(config, st.session_state.creds)
            else:
                st.info("Google API connection required, see the Auth Setup page in the sidebar")


    data = {"youtube": {}, "tags": config["tags"]}
    checked = [title for title in config["youtube"] if config["youtube"][title]["subscribe"]]
    unchecked = [title for title in config["youtube"] if not config["youtube"][title]["subscribe"]]

    for section, subscriptions in [("Subscribed", checked), ("Not Subscribed", unchecked)]:
        with st.expander(section):
            for title in sorted(subscriptions, key=str.casefold):
                entry = config["youtube"][title]
                col1, col2, col3, col4 = st.columns([1, 3, 3, 2])

                with col1:
                    if entry.get("image"):
                        st.image(entry["image"], width=80)
                    else:
                        st.write("No Image")

                with col2:
                    data["youtube"][title] = {
                        "subscribe": st.checkbox(title, value=entry["subscribe"], key=f"sub_{title}"),
                        "tag": entry["tag"],
                        "link": entry["link"],
                        "image": entry.get("image")
                    }

                with col3:
                    if entry["tag"] in list(config["tags"]):
                        idx = list(config["tags"]).index(entry["tag"])
                    else:
                        idx = 0
                    data["youtube"][title]["tag"] = st.selectbox(
                        "Category", options=config["tags"], index=idx, key=f"tag_{title}"
                    )
                with col4:
                    if st.button("Delete", key=title):
                        config["youtube"].pop(title)
                        save_config(config)
                        st.success(f"Deleted Channel: {title}")
                        st.rerun()
    if save_btn:
        save_config(data)
        st.success("Configurations saved!")
        st.rerun()
    
def add_channel_page():
    st.title("Manually Add a Channel")
    config = load_config()
    new_title = st.text_input("Channel Name")
    new_link = st.text_input("Channel URL")
    new_tag = st.selectbox("Category Tag", options=config["tags"])
    image_link = st.text_input("Image Link")
    sub = st.checkbox("Subscribe", value=True)
    if st.button("Add Channel"):
        if new_title and new_link:
            save_channel_config(config, new_title, new_link, new_tag, image_link, sub)
            st.rerun()
            st.success(f"Channel '{new_title}' added!")
        else:
            st.warning("Please fill in all fields to add a channel.")

def manage_tags_page():
    st.title("Add or Remove Tags")
    config = load_config()

    if "tags" not in config:
        config["tags"] = ["other"]

    cols = st.columns([0.7, 0.3])
    with cols[0]:
        new_tag = st.text_input("Add a new tag")
    with cols[1]:
        add_tag = st.button("Add Tag")
    if add_tag and new_tag:
        if new_tag not in config["tags"]:
            config["tags"].append(new_tag)
            save_config(config)
            st.success(f"Added tag: {new_tag}")
            st.rerun()
        else:
            st.warning("Tag already exists")

    st.markdown("---")

    # Display and delete existing tags
    if config.get("tags"):
        for tag in config.get("tags"):
            cols = st.columns([0.2, 0.5])
            with cols[0]:
                st.text(tag)
            with cols[1]:
                if tag != "other":
                    if st.button("Delete", key=f"delete_{tag}"):
                        config["tags"].remove(tag)
                        save_config(config)
                        st.success(f"Deleted tag: {tag}")
                        st.rerun()
    else:
        st.info("No tags available.")


def auth_setup_page():
    st.title("Google OAuth Setup")
    st.markdown("""
    To use YouTube integration, follow these steps:

    1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
    2. Create a new project or use an existing one
    3. Enable the YouTube Data API v3
    4. Create OAuth client credentials (type: Desktop or Web App)
    5. Download the `client_secret.json` file
    6. Upload it below by dragging and dropping or selecting browse

    Restart the app and complete authentication.
    """)
    if st.button("Authenticate"):
        creds = authenticate_youtube()
        print(creds)
        st.session_state.creds = creds

    file = st.file_uploader("Google API Client Secret File", ["json"])
    if file:
        # Save file to this directory
        with open("./client_secret.json", "wb") as f:
            f.write(file.getbuffer())
        st.success("Successfully saved your client_secret.json")

def settings_page():
    st.title("Settings")
    config = load_config()
    current_path = config.get("settings", {}).get("download_path", "")
    
    # Track whether user is editing
    if "editing_download_path" not in st.session_state:
        st.session_state.editing_download_path = not bool(current_path)

    st.subheader("Download Location")

    if not st.session_state.editing_download_path and current_path:
        cols = st.columns([0.85, 0.15])
        cols[0].markdown(f"**Current path:** `{current_path}`")
        if cols[1].button("Edit"):
            st.session_state.editing_download_path = True
    else:
        new_path = st.text_input("Enter path to download folder:", value=current_path, placeholder="/home/user/Downloads")
        
        if new_path and not os.path.isdir(new_path):
            st.error("⚠️ This folder does not exist.")
        else:
            if st.button("Save Path"):
                config.setdefault("settings", {})["download_path"] = new_path
                save_config(config)
                st.session_state.editing_download_path = False
                st.success("✅ Download path saved.")
                st.rerun()

def streamlit_app():
    config = load_config()
    if not config.get("settings") or not config["settings"].get("download_path"):
        settings_page()
    else:
        st.sidebar.title("Navigation")
        if st.query_params.get("code"):
            authenticate_youtube(show_link=False)
        page = st.sidebar.radio("Go to", ["Subscriptions","Add Channel", "Manage Tags", "Auth Setup", "Settings"])

        if "creds" not in st.session_state:
            st.session_state.creds = None

        if page == "Auth Setup":
            auth_setup_page()
        elif page == "Add Channel":
            add_channel_page()
        elif page == "Manage Tags":
            manage_tags_page()
        elif page == "Subscriptions":
            youtube_page()
        elif page == "Settings":
            settings_page()

if __name__ == '__main__':
    # Start the Streamlit app
    streamlit_app()