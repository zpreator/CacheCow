from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.templating import templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tag

router = APIRouter(prefix="/tags")


@router.get("", response_class=HTMLResponse)
async def list_tags(request: Request, db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "tags/index.html", {
        "tags": tags,
        "active_page": "tags",
    })


@router.post("", response_class=HTMLResponse)
async def create_tag(request: Request, db: Session = Depends(get_db), name: str = Form()):
    name = name.strip().lower()
    if name and not db.query(Tag).filter(Tag.name == name).first():
        db.add(Tag(name=name))
        db.commit()
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "tags/_tag_list.html", {
        "tags": tags,
    })


@router.post("/json")
async def create_tag_json(request: Request, db: Session = Depends(get_db), name: str = Form()):
    name = name.strip().lower()
    if not name:
        return JSONResponse({"error": "Name is required"}, status_code=400)
    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing:
        return JSONResponse({"id": existing.id, "name": existing.name})
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return JSONResponse({"id": tag.id, "name": tag.name})


@router.delete("/{tag_id}", response_class=HTMLResponse)
async def delete_tag(request: Request, tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(Tag).get(tag_id)
    if tag and tag.name != "other":
        # Move channels with this tag to "other"
        other = db.query(Tag).filter(Tag.name == "other").first()
        for channel in tag.channels:
            channel.tag_id = other.id
        db.delete(tag)
        db.commit()
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse(request, "tags/_tag_list.html", {
        "tags": tags,
    })
