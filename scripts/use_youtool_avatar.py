import re
import youtool
from urllib.parse import urljoin

yt = youtool.YouTube([None])
base = "https://www.youtube.com"
forms = ["/c/", "/user/", "/@/", "/channel/"]
name = 'Ludwig'

def find_avatar_from_html(html):
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^\"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'<link[^>]+rel="image_src"[^>]+href="([^\"]+)"', html)
    if m:
        return m.group(1)
    return None

for f in forms:
    url = urljoin(base, f + name)
    try:
        r = yt.session.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible)"}, timeout=10)
        r.raise_for_status()
        avatar = find_avatar_from_html(r.text)
        print(url, '->', avatar)
    except Exception as e:
        print(url, 'error', e)

# Try direct channel URL if we can get channel id
try:
    cid = yt.channel_id_from_url('https://www.youtube.com/c/' + name)
    print('channel_id_from_url:', cid)
except Exception as e:
    print('channel_id_from_url error', e)
