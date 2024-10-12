# Youtubedl and Radarr Integration

This project does 3 things:
1. Hosts a web UI for managing youtube downloads (Docker, streamlit)
2. A python script for downloading youtube videos from curated list of creators (via cronjob)
3. A python script for adding movies to Radarr from my letterboxd wishlist (via cronjob)

## Web UI

The webui presents all your youtube subsriptions with checkboxes to curate. 
*Only edits a config file, which is then used in the python script for youtube download.

![image](https://github.com/user-attachments/assets/81ae0e0d-4a30-464f-bbe9-a33756af8d3f)

## Youtube Download

Uses the config file generated from the Web UI to download youtube videos using youtubedl

## Letterboxd to Radarr

Scrapes the public watchlist of a letterboxd account to add to Radarr
