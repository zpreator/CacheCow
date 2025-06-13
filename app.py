from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import streamlit as st
import os
from dotenv import load_dotenv
from utils import load_config, save_config, PROGRESS_FILE, RUN_NOW_FILE
import subprocess
import re
from pathlib import Path
import psutil
import json
import time
import hashlib

load_dotenv()

# OAuth Stuff for linking with Google API (optional)
CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

# Function to verify login
def login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            hashed_input = hashlib.sha256(password.encode()).hexdigest()
            if username == os.environ.get("STREAMLIT_USER") and hashed_input == os.environ.get("STREAMLIT_PASS"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password")
        st.stop()

def backwards_compat(config):
    if not config.get("settings"):
        config["settings"] = {}
    if not config["settings"].get("download_path"):
        download_path = os.environ.get("DOWNLOAD_PATH", "/app/downloads")
        if "download_path" in config["settings"]:
            config["settings"]["download_path"] = download_path
        else:
            config["settings"] = {"download_path": download_path}
        save_config(config)
        print(f"Set the download path to {config['settings']['download_path']}")
    
    # Ensure all youtube channel configs have required keys with defaults
    required_keys = {
        "subscribe": True,
        "tag": config["tags"][0] if config.get("tags") else "other",
        "link": "",
        "image": "https://placehold.co/400",
        "use_global_settings": True,
        "max_duration": "60",
        "download_all": False,
        "days": "8",
        "items": "5",
        "include_keywords": None,
        "exclude_keywords": None
    }
    if "youtube" in config:
        for title, entry in config["youtube"].items():
            for key, default in required_keys.items():
                if key not in entry:
                    entry[key] = default
        save_config(config)

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

# Merge the fetched youtube subscriptions with the current config
def refresh_data(config, creds):
    subscriptions = get_subscriptions(creds)

    # Keep existing settings for old subscriptions, add new ones as False
    for sub in subscriptions:
        title = sub["snippet"]["title"]
        if title not in config["youtube"]:
            channel_id = sub["snippet"]["resourceId"]["channelId"]
            channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
            thumbnail_url = sub["snippet"]["thumbnails"]["default"]["url"]
            config["youtube"][title] = {
                "subscribe": True,
                "tag": config["tags"][0],  # Default to the first tag in config['tags']
                "link": channel_url,
                "image": thumbnail_url,
                "use_global_settings": True,
                "max_duration": "60",  # Default max duration in minutes
                "download_all": False,
                "days": "8",
                "items": "5",
                "include_keywords": None,
                "exclude_keywords": None
            }

    save_config(config)
    return config

def save_channel_config(config, title, url, tag, image, use_global, max_duration, sub, download_all, days, items,
                        include_keywords, exclude_keywords):
    if not title:
        st.error("Please provide a Channel Name")
        return
    if not url:
        st.error("Please provide a valid youtube URL. Hint, navigate to the channel, click 'videos' and copy the URL in the address bar")
        return
    if not image:
        image = "https://placehold.co/400"
    config["youtube"][title] = {
        "subscribe": sub,
        "tag": tag,
        "link": url,
        "image": image,
        "use_global_settings": use_global,
        "max_duration": max_duration,
        "download_all": download_all,
        "days": days,
        "items": items,
        "include_keywords": include_keywords,
        "exclude_keywords": exclude_keywords
    }
    save_config(config)

def youtube_page():
    st.title("Subscriptions")
    with st.expander("ℹ️ How Subscriptions Work", expanded=False):
        st.markdown("""
        This page lets you manage the channels you've **subscribed to within this app**.

        🔧 **Each channel has individual settings** — you can customize download filters, keywords, or max video length per channel.

        ❗ **Important:** These subscriptions are **separate from your actual YouTube account**.  
        Adding or deleting channels here won’t affect your YouTube account.

        🔁 If you click **"Sync YouTube Subscriptions"**, the app will re-fetch your real YouTube subscriptions and overwrite this list.  
        That means any manual deletes you did here will be undone.

        ✅ Subscribing to a channel in this app simply means:  
        **"Download this channel’s videos using the settings I’ve chosen."**
        """)
    with st.expander("🧠 Why Limit Downloads?", expanded=False):
        st.markdown("""
        By default, this app **limits how many videos are downloaded per channel** — both in terms of:

        - 🕒 **How recent** the videos are (e.g., only videos from the past 7 days)
        - 🔢 **How many** videos to download (e.g., up to 5 videos)

        These limits are especially useful when you're just starting out or syncing a new channel for the first time:

        - ✅ Prevents accidentally downloading **entire playlists with hundreds or thousands of videos**
        - 💾 Saves **disk space** and avoids overwhelming your system
        - ⚡ Makes the initial setup **faster and safer**

        ---
        If you’re dealing with a **small playlist** (like To Download) that you do want to download completely, you can check the  
        **"Download All"** option. This will ignore the recent video and count limits and grab everything.

        *(Use this with care — especially on large playlists!)*  
        """)
    config = load_config()

    cols = st.columns(2)
    # with cols[0]:
    #     save_btn = st.button("Save Changes")
    # with cols[1]:
    if st.button("Sync Youtube Subscriptions"):
        st.session_state.creds = authenticate_youtube()
        if st.session_state.creds:
            config = refresh_data(config, st.session_state.creds)
        else:
            st.info("Google API connection required, see the Auth Setup page in the sidebar")


    # data = {"youtube": {}, "tags": config["tags"]}
    checked = [title for title in config["youtube"] if config["youtube"][title]["subscribe"]]
    unchecked = [title for title in config["youtube"] if not config["youtube"][title]["subscribe"]]

    for section, subscriptions in [("Subscribed", checked), ("Not Subscribed", unchecked)]:
        st.subheader(section)
        for title in sorted(subscriptions, key=str.casefold):
            entry = config["youtube"][title]
            col1, col2 = st.columns([0.2, 0.8])
            with col1:
                if entry.get("image"):
                    st.image(entry["image"], width=80)
                else:
                    st.write("No Image")
            with col2:
                with st.expander(f"{title}  --- {entry['tag']}"):
                    use_global_settings = st.checkbox(
                            "Use Global Settings", 
                            value=entry.get("use_global_settings", True), 
                            key=f"use_global_{title}",
                            help="If you uncheck this, you can set custom settings for this channel"
                        )
                    download_all = st.checkbox(
                        "Download All", 
                        value=entry.get("download_all", False), 
                        key=f"download_{title}", 
                        help="❗Selecting this will download all videos in this playlist which could mean thousands. Use with caution❗"
                    )
                    with st.form(title, clear_on_submit=False):
                        
                        # Get existing values or set default ones
                        default_subscribed = entry["subscribe"]
                        if entry["tag"] in list(config["tags"]):
                            default_tag_idx = list(config["tags"]).index(entry["tag"])
                        else:
                            default_tag_idx = 0
                        default_days = int(entry.get("days", "8"))
                        default_items = int(entry.get("items", "5"))
                        # default_download_all = entry.get("download_all", False)
                        include_keywords = config["youtube"][title].get("include_keywords")
                        exclude_keywords = config["youtube"][title].get("exclude_keywords")

                        # Provide UI to edit directly to the config. These changes are only applied on save of this section
                        config["youtube"][title]["subscribe"] = st.checkbox(
                            "Subscribed", 
                            value=default_subscribed, 
                            key=f"sub_{title}"
                        )
                        
                        
                            
                        
                        if use_global_settings:
                            config["youtube"][title]["tag"] = st.selectbox(
                                    "Category", 
                                    options=config["tags"], 
                                    index=default_tag_idx, 
                                    key=f"tag_{title}",
                                    help="Use tags to categorize your media. See the 'Manage Tags' page for more info"
                                )
                            cols = st.columns(2)
                        else:
                            cols = st.columns(2)
                            with cols[0]:
                                config["youtube"][title]["tag"] = st.selectbox(
                                    "Category", 
                                    options=config["tags"], 
                                    index=default_tag_idx, 
                                    key=f"tag_{title}",
                                    help="Use tags to categorize your media. See the 'Manage Tags' page for more info"
                                )
                            with cols[1]:
                                config["youtube"][title]["max_duration"] = str(st.number_input(
                                    "Max Duration (minutes)",
                                    value=60,
                                    key=f"duration_{title}",
                                    help="Only download videos with a duration less than this value (in minutes)"
                                ))
                            
                            
                            if not download_all:
                                with cols[0]:
                                    config["youtube"][title]["days"] = str(st.number_input(
                                        "Get Videos Since X Days Ago", 
                                        min_value=0, 
                                        value=default_days, 
                                        key=f"days_{title}",
                                        help="This option will cap the downloads to only look within the previous X days"
                                    ))
                                with cols[1]:
                                    config["youtube"][title]["items"] = str(st.number_input(
                                        "Get Most Recent X Videos", 
                                        min_value=0, 
                                        value=default_items, 
                                        key=f"items_{title}",
                                        help="This option will cap the downloads to only get the previous X videos"
                                    ))
                        
                        
                            with cols[0]:
                                config["youtube"][title]["include_keywords"] = st.text_input(
                                    "Keywords to include (separated by comma, leave blank for none)", 
                                    value=include_keywords, 
                                    key=f"include_{title}",
                                    help="Only download videos if they include these keywords"
                                )
                            with cols[1]:
                                config["youtube"][title]["exclude_keywords"] = st.text_input(
                                    "Keywords to exclude (separated by comma, leave blank for none)", 
                                    value=exclude_keywords, 
                                    key=f"exclude_{title}",
                                    help="Only download videos that do NOT include these keywords"
                                )
                        config["youtube"][title]["download_all"] = download_all
                        config["youtube"][title]["use_global_settings"] = use_global_settings
                        with cols[0]:
                            if st.form_submit_button("💾 Save"):
                                save_config(config)
                                st.success(f"Saved settings for {title}")
                                st.rerun()
                        with cols[1]:
                            if st.form_submit_button("❗Delete"):
                                config["youtube"].pop(title)
                                save_config(config)
                                st.success(f"Deleted Channel: {title}")
                                st.rerun()
    
    
def add_channel_page():
    st.title("Manually Add a Channel")
    with st.expander("📺 Set Up a Custom YouTube Playlist for Downloads"):
        st.markdown("""
    To automatically download videos later, follow these steps to create and share a playlist:

    ---

    #### 1. **Create a Playlist in YouTube**
    - Go to [YouTube](https://www.youtube.com).
    - Click your profile picture → **"Your Channel"**.
    - Click the **"Playlists"** tab, then **"New playlist"**.
    - Give it a name like `"YT-DL Watchlist"`.

    ---

    #### 2. **Make It Public (or Unlisted)**
    - After creating the playlist, open it.
    - Click the **pencil/edit icon** near the title.
    - Under **"Visibility"**, choose **Public** or **Unlisted**.
    - **Public**: anyone can see it.
    - **Unlisted**: only people with the link can access (recommended).

    ---

    #### 3. **Get the Playlist Link**
    - While viewing the playlist, copy the URL from your browser.
    - It will look like this:
    ```
    https://www.youtube.com/playlist?list=PLabc123xyz...
    ```

    ---

    #### 4. **Add It to the App**
    - Fill in the Channel name
    - Paste the playlist link into the **Channel Link** field.
    - Choose a tag (optional) and click **Subscribe**.
    - **Important**: select Download All in order to allow any video outside of the default 8 days or most recent 5 videos

    Once added, the app will automatically pull videos from this playlist during scheduled downloads.

    """)

    config = load_config()
    new_title = st.text_input("Channel Name *", help="This is a custom field for your convenience. Name it whatever you want")
    new_link = st.text_input("Channel URL *", help="Technically, this needs to be a playlist URL. I prefer to use a channel's 'videos' playlist to get all their content")
    new_tag = st.selectbox("Category Tag", options=config["tags"], help="Use tags to categorize your media. See the 'Manage Tags' page for more info")
    image_link = st.text_input("Image Link", help="On youtube, you can right click an image (your profile for example) and 'Open Image in New Tab' and copy the address")
    download_all = st.checkbox("Download All", help="Selecting this will download all videos in this playlist, use with caution!")
    include_keywords = st.text_input("Keywords to include (separated by comma, leave blank to ignore this setting)", help="Only download videos if they include these keywords")
    exclude_keywords = st.text_input("Keywords to exclude (separated by comma, leave blank to ignore this setting)", help="Only download videos that do NOT include these keywords")
    use_global = st.checkbox("Use Global Settings", value=True, help="If you uncheck this, you can set custom settings for this channel")
    if use_global:
        max_duration = str(st.number_input(
                                "Max Duration (minutes)",
                                value=60,
                                help="Only download videos with a duration less than this value (in minutes)"
                            ))
        if not download_all:
            days = str(st.number_input("Get Videos Since X Days Ago (Set to 0 for infinity)", min_value=0, value=8, help="This option will cap the downloads to only look within the previous X days"))
            items = str(st.number_input("Get Most Recent X Videos (Set to 0 for infinity)", min_value=0, value=5, help="This option will cap the downloads to only get the previous X videos"))
        else:
            days = "0"
            items = "0"
    else:
        max_duration = None
        days = None
        items = None
    sub = st.checkbox("Subscribe", value=True)
    if st.button("Add Channel"):
        if new_title and new_link:
            save_channel_config(config, new_title, new_link, new_tag, image_link, use_global, max_duration, sub, download_all, days, items, include_keywords, exclude_keywords)
            st.success(f"Channel '{new_title}' added!")
            st.rerun()
        else:
            st.warning("Please fill in all required * fields to add a channel.")

def manage_tags_page():
    st.title("Add or Remove Tags")

    with st.expander("Tags Folder Structure"):
        st.markdown(""" Use tags to split the downloaded videos into sections. This example shows Cooking and other which I use as separate Plex Libraries""")
        st.image("images/image.png")
        
        
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
    st.title("🔐 YouTube API Setup (First-Time Only)")
    with st.expander("Detailed Instructions"):
        render_markdown_with_images("youtube-api.md", skip_first_line=True)

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

    st.subheader("💾 Download Status")
    # Check if process is running (from earlier discussions)
    is_running = os.path.exists(PROGRESS_FILE)
    help = ""
    if is_running:
        help = "The downloader is currently running..."
    cols = st.columns([0.3, 0.3])
    with cols[0]:
        if st.button("Run Downloader Now", disabled=is_running, help=help):
            with open(RUN_NOW_FILE, "w") as f:
                f.write("manual run\n")
            st.success("Downloader will run shortly!")
            st.rerun()
    with cols[1]:
        if st.button("🔁"):
            st.rerun()
    if is_running:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
            name = data.get("name", "")
            current = data.get("index", 0)
            total = data.get("total", 1)  # Avoid division by 0
            progress = current / total
            st.progress(progress, name)
            st.text(f"Downloaded videos for {current} of {total} channels")

        else:
            st.info("Progress data not yet available")

    current_path = config.get("settings", {}).get("download_path", "")
    env_path = os.environ.get("DOWNLOAD_PATH")
    
    # Track whether user is editing
    if "editing_download_path" not in st.session_state:
        st.session_state.editing_download_path = not bool(current_path)

    # st.markdown("---")
    st.subheader("Global Settings")
    st.markdown("These settings will be used for all channels unless you override them in the channel settings")
    with st.form("global_settings"):
        minutes_between_runs = st.number_input("⏱️ Minutes Between Runs", min_value=1, value=int(config["settings"].get("minutes_between_runs", 60)), help="How often to run the downloader script")
        random_interval_lower = st.number_input("⏳ Random Interval Lower Bound (seconds)", min_value=0, value=int(config["settings"].get("random_interval_lower", 15)), help="The lower bound for the random interval between runs")
        random_interval_upper = st.number_input("⏳ Random Interval Upper Bound (seconds)", min_value=0, value=int(config["settings"].get("random_interval_upper", 45)), help="The upper bound for the random interval between runs")
        max_duration = st.number_input("🎬 Max Duration (minutes)", min_value=1, value=int(config["settings"].get("max_duration", 60)), help="Don't download videos longer than this")
        days = st.number_input("📅 Get Videos Since X Days Ago", min_value=0, value=int(config["settings"].get("days", 8)), help="This option will cap the downloads to only look within the previous X days")
        items = st.number_input("🔢 Get Most Recent X Videos", min_value=0, value=int(config["settings"].get("items", 5)), help="This option will cap the downloads to only get the previous X videos")
        if st.form_submit_button("Update Global Settings"):
            config["settings"]["minutes_between_runs"] = str(minutes_between_runs)
            config["settings"]["max_duration"] = str(max_duration)
            config["settings"]["days"] = str(days)
            config["settings"]["items"] = str(items)
            config["settings"]["random_interval_lower"] = str(random_interval_lower)
            config["settings"]["random_interval_upper"] = str(random_interval_upper)
            save_config(config)
            st.success("Duration setting saved.")

    st.subheader("Download Location")

    with st.expander("Note..."):
        st.markdown(f"""
        For security, the app only has access to folders inside of:
                    
        ```
        {env_path}    
        ```
                    
        To change this, edit the .env file and restart the app or re-run the setup.sh. See the README for more info.

        If you want to update the download path WITHIN that, edit the Current Path below
        """)
    
    
    if not st.session_state.editing_download_path and current_path:
        cols = st.columns([0.85, 0.15])
        cols[0].markdown(f"**Current path:** `{current_path}`", help="This is where videos will be saved")
        if cols[1].button("Edit"):
            st.session_state.editing_download_path = True
    else:
        new_path = st.text_input("Enter path to download folder:", value=current_path, placeholder=env_path)
        
        if new_path and not os.path.isdir(new_path):
            st.error("⚠️ This folder does not exist.")
        else:
            if st.button("Save Path"):
                config["settings"]["download_path"] = new_path
                save_config(config)
                st.session_state.editing_download_path = False
                st.success("✅ Download path saved.")

    # st.markdown("---")
    st.subheader("🧹 Cleaning")
    with st.form("cleaning_settings"):
        do_clean = st.checkbox("Remove Old Files", value=config["settings"].get("remove_old_files", True))
        days = config["settings"].get("clean_threshold", 90)
        if do_clean:
            download_path = config["settings"].get("download_path")
            st.warning(f"This will remove .mp4 files in: {download_path}")
            days = st.number_input("Days Before Removal", min_value=1, value=days, key="clean_days")

        if st.form_submit_button("Update Cleaning Settings"):
            config["settings"]["remove_old_files"] = do_clean
            config["settings"]["clean_threshold"] = days
            save_config(config)
            st.success("Cleaning settings updated.")

    # st.markdown("---")
    

def render_markdown_with_images(path: str, skip_first_line=False):
    """
    Render markdown file and replace image references with st.image().
    
    Parameters:
        path (str): Path to the markdown file.
        skip_first_line (bool): If True, skip the first line of the file.
    """
    image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
    with open(path, "r") as f:
        lines = f.readlines()

    if skip_first_line:
        lines = lines[1:]

    for line in lines:
        match = image_pattern.search(line)
        if match:
            alt_text, image_path = match.groups()
            image_file = Path(image_path)
            if image_file.exists():
                st.image(str(image_file), caption=alt_text)
            else:
                st.warning(f"Image not found: {image_path}")
        else:
            st.markdown(line, unsafe_allow_html=True)

def readme_page():
    render_markdown_with_images("README.md")

def logs_page():
    st.title("📦 Docker Logs Viewer")

    container_name = "cachecow-streamlit-app-1"  # or whatever your container is called
    num_lines = st.slider("How many lines to show?", 10, 500, 100)

    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(num_lines), container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        st.code(result.stdout, language="bash")

        if result.stderr:
            st.error(result.stderr)

    except Exception as e:
        st.error(f"Error getting logs: {e}")
    
def streamlit_app():
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    login()
    config = load_config()
    backwards_compat(config)
    st.sidebar.title("Navigation")
    if st.query_params.get("code"):
        authenticate_youtube(show_link=False)
    page = st.sidebar.radio("Go to", ["Subscriptions","Add Channel", "Manage Tags", "Auth Setup", "Settings", "Logs", "README"])

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
    elif page == "Logs":
        logs_page()
    elif page == "README":
        readme_page()

if __name__ == '__main__':
    # Start the Streamlit app
    streamlit_app()
