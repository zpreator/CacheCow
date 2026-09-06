#!/usr/bin/env python3
"""Find (and optionally repair) videos whose picture freezes partway through.

A partially downloaded video stream still produces a container whose header
advertises the full duration, so nothing errors at download time and players
show a normal length — the picture just freezes when the video track runs out
while the audio keeps playing. This walks a download directory and reports every
file with that defect.

    python scripts/verify_library.py /path/to/downloads
    python scripts/verify_library.py /path/to/downloads --fix

With --fix, each broken file is deleted and its entry removed from the yt-dlp
archive, so the next CacheCow run downloads it again.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.downloader import (  # noqa: E402
    _remove_from_archive,
    verify_video_integrity,
)

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".m4v"}


def find_videos(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                yield os.path.join(dirpath, name)


def load_id_map():
    """Map file_path -> youtube_id from the database.

    Downloads are named "<uploader> - <title>.<ext>" with no video id in the
    filename, so the database is the only reliable way to match a file back to
    its archive entry.
    """
    try:
        from app.database import SessionLocal
        from app.models import Video
    except Exception as e:
        print(f"(could not open database, files will be deleted but not un-archived: {e})")
        return {}

    db = SessionLocal()
    try:
        rows = db.query(Video.file_path, Video.youtube_id).all()
        return {path: vid for path, vid in rows if path}
    except Exception as e:
        print(f"(database read failed: {e})")
        return {}
    finally:
        db.close()


def youtube_id_for(path, id_map):
    """Resolve a file to its youtube id, tolerating moved/renamed parent dirs."""
    if path in id_map:
        return id_map[path]
    name = os.path.basename(path)
    return next((vid for p, vid in id_map.items() if os.path.basename(p) == name), "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="download directory to scan")
    parser.add_argument("--fix", action="store_true",
                        help="delete broken files and un-archive them so they re-download")
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print(f"Not a directory: {args.path}")
        return 1

    id_map = load_id_map() if args.fix else {}
    videos = list(find_videos(args.path))
    print(f"Scanning {len(videos)} video file(s) under {args.path}\n")

    broken = []
    for path in videos:
        ok, detail = verify_video_integrity(path)
        if ok:
            continue
        broken.append(path)
        print(f"BROKEN  {os.path.relpath(path, args.path)}\n        {detail}")
        if args.fix:
            try:
                os.remove(path)
                print("        deleted")
            except OSError as e:
                print(f"        could not delete: {e}")
                continue
            vid = youtube_id_for(path, id_map)
            if vid and _remove_from_archive(vid):
                print(f"        un-archived {vid} — will download again next run")
            elif not vid:
                print("        WARNING: no database entry; not un-archived — "
                      "it will NOT re-download automatically")

    print(f"\n{len(broken)} broken / {len(videos)} scanned")
    if broken and not args.fix:
        print("Re-run with --fix to delete them and queue them for re-download.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
