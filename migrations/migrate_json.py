"""
One-time migration: data/config.json -> SQLite

Run from the project root:
    python -m migrations.migrate_json
"""
import json
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine
from app.models import Channel, Settings, Tag


def migrate():
    Base.metadata.create_all(engine)
    db = SessionLocal()

    config_path = "data/config.json"
    if not os.path.exists(config_path):
        print(f"No {config_path} found. Nothing to migrate.")
        return

    with open(config_path) as f:
        config = json.load(f)

    # 1. Migrate tags
    tag_map = {}
    for tag_name in config.get("tags", ["other"]):
        existing = db.query(Tag).filter(Tag.name == tag_name).first()
        if existing:
            tag_map[tag_name] = existing.id
        else:
            tag = Tag(name=tag_name)
            db.add(tag)
            db.flush()
            tag_map[tag_name] = tag.id

    # Ensure "other" exists
    if "other" not in tag_map:
        tag = Tag(name="other")
        db.add(tag)
        db.flush()
        tag_map["other"] = tag.id

    # 2. Migrate settings
    s = config.get("settings", {})
    existing_settings = db.query(Settings).first()
    if not existing_settings:
        settings = Settings(
            download_path=s.get("download_path", "/app/downloads"),
            minutes_between_runs=int(s.get("minutes_between_runs", 60)),
            random_interval_lower=int(s.get("random_interval_lower", 15)),
            random_interval_upper=int(s.get("random_interval_upper", 45)),
            max_duration=int(s.get("max_duration", 60)),
            days=int(s.get("days", 8)),
            items=int(s.get("items", 5)),
            remove_old_files=s.get("remove_old_files", True),
            clean_threshold=int(s.get("clean_threshold", 90)),
        )
        db.add(settings)
    else:
        print("Settings already exist, skipping.")

    # 3. Migrate channels
    migrated = 0
    skipped = 0
    for name, entry in config.get("youtube", {}).items():
        existing = db.query(Channel).filter(Channel.name == name).first()
        if existing:
            skipped += 1
            continue

        tag_name = entry.get("tag", "other")
        tag_id = tag_map.get(tag_name, tag_map.get("other"))

        channel = Channel(
            name=name,
            link=entry.get("link", ""),
            image=entry.get("image", ""),
            subscribe=entry.get("subscribe", True),
            tag_id=tag_id,
            use_global_settings=entry.get("use_global_settings", True),
            download_all=entry.get("download_all", False),
            max_duration=int(entry.get("max_duration", 60)),
            days=int(entry.get("days", 8)),
            items=int(entry.get("items", 5)),
            include_keywords=entry.get("include_keywords") or None,
            exclude_keywords=entry.get("exclude_keywords") or None,
        )
        db.add(channel)
        migrated += 1

    db.commit()
    db.close()

    print(f"Migration complete:")
    print(f"  Tags: {len(tag_map)} created/found")
    print(f"  Channels: {migrated} migrated, {skipped} skipped (already exist)")
    print(f"  Settings: migrated")


if __name__ == "__main__":
    migrate()
