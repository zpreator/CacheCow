import requests
import re
from requests import session
from bs4 import BeautifulSoup
from datetime import datetime

match_imdb = re.compile(r"^https?://www.imdb.com")
match_tmdb = re.compile(r"^https?://www.themoviedb.org")

base_url = "https://letterboxd.com/"

username = "darthpreator"

# Radarr API configurations
RADARR_URL = 'http://localhost:7878/api/v3'
API_KEY = '4e4f44255f024b14a1735136e693d7e2'

# def add_movie_to_radarr(movie_title, movie_year):
#     # Prepare the movie data
#     movie_data = {
#         "title": movie_title,
#         "year": movie_year,
#         "qualityProfileId": 1,  # Adjust the quality profile ID as needed
#         "titleSlug": movie_title.lower().replace(" ", "-"),
#         "images": [],
#         "path": "",  # Optional: specify a custom path if desired
#         "monitored": True,
#         "minimumAvailability": "released",  # Adjust based on your needs
#     }

#     # Send the request to add the movie
#     response = requests.post(
#         f'{RADARR_URL}/movie',
#         json=movie_data,
#         headers={'X-Api-Key': API_KEY}
#     )

#     if response.status_code == 201:
#         print(f'Successfully added movie: {movie_title} ({movie_year})')
#     else:
#         print(f'Failed to add movie: {response.status_code} - {response.text}')

def add_movie_to_radarr(movie_title, movie_year):
    # Search for the movie in Radarr to get the movie ID and other metadata
    search_url = f'{RADARR_URL}/movie/lookup'
    params = {'term': f'{movie_title} {movie_year}'}
    
    search_response = requests.get(search_url, headers={'X-Api-Key': API_KEY}, params=params)
    
    if search_response.status_code == 200:
        search_results = search_response.json()
        
        if len(search_results) == 0:
            print(f"Movie not found: {movie_title} ({movie_year})")
            return False
        
        # Use the first result (or handle cases with multiple results as you see fit)
        movie_info = search_results[0]

        # Prepare the movie data to send to Radarr
        movie_data = {
            "title": movie_info['title'],
            "year": movie_info['year'],
            "qualityProfileId": 4,  # Adjust the quality profile ID as needed
            "titleSlug": movie_info['titleSlug'],
            "images": movie_info['images'],
            "tmdbId": movie_info['tmdbId'],
            "path": f"/home/glados/SharedMedia/Media/Movies/Other/{movie_info['title']}",  # Adjust the path as needed
            "monitored": True,
            "minimumAvailability": "released",  # Use a valid enum value
            "addOptions": {
                "searchForMovie": True  # Tells Radarr to search and download immediately
            }
        }

        # Add the movie to Radarr
        add_movie_url = f'{RADARR_URL}/movie'
        response = requests.post(add_movie_url, json=movie_data, headers={'X-Api-Key': API_KEY})

        if response.status_code == 201:
            print(f'Successfully added movie: {movie_title} ({movie_year})')
            return True
        elif response.status_code == 400:
            # Check if the movie already exists
            if "MovieExistsValidator" in str(response.json()):
                # print(f'Movie already exists: {movie_title} ({movie_year})')
                pass
            else:
                print(f'Failed to add movie: {response.status_code} - {response.text}')
        else:
            print(f'Failed to add movie: {response.status_code} - {response.text}')
    else:
        print(f'Failed to search for movie: {search_response.status_code} - {search_response.text}')
    return False

def get_watchlist(letterboxd_url):
    s = session()
    watchlist_url = letterboxd_url.rstrip("/")
    if not watchlist_url.startswith("https://"):
        watchlist_url = f"{base_url}{watchlist_url}"
    if not watchlist_url.endswith("watchlist"):
        watchlist_url += "/watchlist"
    watchlist_url += "/"

    # Get first page, gather general data
    r = s.get(watchlist_url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Get total number of movies
    m = soup.find("span", attrs={"class": "js-watchlist-count"})
    total_movies = int(m.text.split()[0]) if m else 0
    print(f"Found a total of {total_movies} movies")

    # Get total number of pages
    paginator = soup.find_all("li", attrs={"class": "paginate-page"})
    page_count = int(paginator[-1].text) if paginator else 1
    last_page_index = page_count + 1

    # Start processing movies
    movie_data = []
    for page in range(1, last_page_index):
        if page > 1:
            r = s.get(watchlist_url + "/page/%i/" % page)
            soup = BeautifulSoup(r.text, "html.parser")

        ul = soup.find("ul", attrs={"class": "poster-list"})
        if ul is None:
            continue
        movies = ul.find_all("li")
        movies_on_page = len(movies)

        print(f"Gathering movies on page {page} (contains {movies_on_page} movies)\n")

        
        for movie in movies:
            title, year, desc, link = extract_metadata(movie, s)
            if all([title, year, desc, link]):
                movie_data.append((title, year, desc, link))
    return movie_data

def extract_title_and_year(movie_string):
    # Use a regular expression to extract the title and year
    match = re.match(r"(.+)\s\((\d{4})\)", movie_string)
    if match:
        title = match.group(1)
        year = match.group(2)
        return title, year
    else:
        return None, None
    
def extract_metadata(movie, s):
    try:
        movie_url = base_url + "film/" + movie.div.attrs["data-film-slug"]
        movie_page = s.get(movie_url)
        movie_soup = BeautifulSoup(movie_page.text, "html.parser")

        movie_title = movie_soup.find("meta", attrs={"property": "og:title"}).attrs["content"]
        movie_title, year = extract_title_and_year(movie_title)
        # print("Adding", movie_title)

        # Find the IMDb or TMDb link
        movie_link = movie_soup.find("a", attrs={"href": [match_imdb, match_tmdb]}).attrs["href"]
        if movie_link.endswith("/maindetails"):
            movie_link = movie_link[:-11]

        movie_description = movie_soup.find("meta", attrs={"property": "og:description"})
        movie_description = movie_description.attrs["content"].strip() if movie_description else "No description"

        # Write movie data to CSV
        return movie_title, year, movie_description, movie_link
    except Exception as e:
        print(f"Failed to process movie: {movie_url} - {e}")
        return None, None, None


def main():
    movies = get_watchlist(username)

    scraped_movies = []
    for movie in movies:
        title, year, desc, link = movie
        # print(title, year)
        scraped_movies.append({"title": title, "year": year})

    added_movies = []
    for movie in scraped_movies:
        added = add_movie_to_radarr(movie['title'], movie['year'])
        if added:
            added_movies.append(movie)
            break

    with open("/home/glados/pythonscripts/letterboxd_to_radarr.txt", "w") as file:
        file.write(f"Ran on: {datetime.now().isoformat()}\n")
        for movie in added_movies:
            file.write(f"Added: {movie}\n")

def get_quality_profiles():
    # Define the URL for the quality profile endpoint
    profiles_url = f'{RADARR_URL}/qualityProfile'
    
    # Make the GET request to retrieve the profiles
    response = requests.get(profiles_url, headers={'X-Api-Key': API_KEY})
    
    if response.status_code == 200:
        profiles = response.json()
        
        # Print each profile's name and ID
        for profile in profiles:
            print(f"Profile ID: {profile['id']}, Name: {profile['name']}")
    else:
        print(f"Failed to fetch profiles: {response.status_code} - {response.text}")


if __name__ == "__main__":
    main()
    # get_quality_profiles()
