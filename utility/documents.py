from fastapi import HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import os
import shutil
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text  # Import text for raw SQL queries
from helpers.database import get_db

class DocumentMetadata(BaseModel):
    title: Optional[str] = Field(None, description="Title of the document")
    tags: Optional[List[str]] = Field(None, description="Tags associated with the document")
    permissions: Optional[List[str]] = Field(None, description="Permissions for the document")

    @field_validator("tags", mode="before")
    def validate_tags(cls, value):
        if value and not isinstance(value, list):
            raise ValueError("Tags must be a list of strings")
        return value

    @field_validator("permissions", mode="before")
    def validate_permissions(cls, value):
        if value and not isinstance(value, list):
            raise ValueError("Permissions must be a list of strings")
        return value

def upload_document(file: UploadFile, title: str, tags: List[str], permissions: List[str], uploaded_by: int, db: Session, folder_id: Optional[int] = None):
    # Check if the user exists
    cursor = db.execute(text("SELECT id FROM users WHERE id = :uploaded_by"), {"uploaded_by": uploaded_by})
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=400, detail="User does not exist")
    
    # Generate a unique document ID and save the file
    doc_id = str(uuid.uuid4())
    file_path = f"uploads/{doc_id}_{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Insert the document into the database
    db.execute(
        text("""
            INSERT INTO documents (document_id, title, file_path, uploaded_by, last_updated, folder_id)
            VALUES (:doc_id, :title, :file_path, :uploaded_by, :last_updated, :folder_id)
        """),
        {
            "doc_id": doc_id,
            "title": title,
            "file_path": file_path,
            "uploaded_by": uploaded_by,
            "last_updated": datetime.now(),
            "folder_id": folder_id  # Associate the document with the folder if provided
        }
    )
    
    # Handle tags
    for tag in tags:
        db.execute(text("INSERT INTO tags (tag_name) VALUES (:tag) ON DUPLICATE KEY UPDATE tag_name=tag_name"), {"tag": tag})
        tag_id = db.execute(text("SELECT tag_id FROM tags WHERE tag_name = :tag"), {"tag": tag}).fetchone()[0]
        db.execute(text("INSERT INTO document_tags (document_id, tag_id) VALUES (:doc_id, :tag_id)"), {"doc_id": doc_id, "tag_id": tag_id})
    
    # Handle permissions
    for permission in permissions:
        db.execute(text("INSERT INTO permissions (document_id, user_email) VALUES (:doc_id, :user_email)"), {"doc_id": doc_id, "user_email": permission})
    
    db.commit()
    return {"document_id": doc_id, "message": "Upload successful"}

def get_document_metadata(document_id: str, db: Session):
    document = db.execute(text("SELECT * FROM documents WHERE document_id = :document_id"), {"document_id": document_id}).mappings().fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    tags = db.execute(
        text("SELECT tag_name FROM tags JOIN document_tags ON tags.tag_id = document_tags.tag_id WHERE document_tags.document_id = :document_id"),
        {"document_id": document_id}
    ).mappings().fetchall()
    
    permissions = db.execute(text("SELECT user_email FROM permissions WHERE document_id = :document_id"), {"document_id": document_id}).mappings().fetchall()
    
    uploaded_by_result = db.execute(text("SELECT email FROM users WHERE id = :id"), {"id": document["uploaded_by"]}).mappings().fetchone()
    uploaded_by = uploaded_by_result["email"] if uploaded_by_result else None  # Access the email by key
    
    return {
        "document_id": document_id,
        "title": document["title"],
        "tags": [tag["tag_name"] for tag in tags],
        "uploaded_by": uploaded_by,
        "permissions": [permission["user_email"] for permission in permissions]
    }

def download_document(document_id: str, db: Session):
    document = db.execute(text("SELECT file_path FROM documents WHERE document_id = :document_id"), {"document_id": document_id}).mappings().fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = document["file_path"]
    return FileResponse(file_path, media_type='application/octet-stream', filename=os.path.basename(file_path))

def edit_document_metadata(document_id: str, metadata: DocumentMetadata, db: Session):
    document = db.execute(text("SELECT * FROM documents WHERE document_id = :document_id"), {"document_id": document_id}).mappings().fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if metadata.title is not None:
        db.execute(text("UPDATE documents SET title = :title WHERE document_id = :document_id"), {"title": metadata.title, "document_id": document_id})
    
    if metadata.tags is not None:
        db.execute(text("DELETE FROM document_tags WHERE document_id = :document_id"), {"document_id": document_id})
        for tag in metadata.tags:
            db.execute(text("INSERT INTO tags (tag_name) VALUES (:tag) ON DUPLICATE KEY UPDATE tag_name=tag_name"), {"tag": tag})
            tag_id = db.execute(text("SELECT tag_id FROM tags WHERE tag_name = :tag"), {"tag": tag}).fetchone()[0]
            db.execute(text("INSERT INTO document_tags (document_id, tag_id) VALUES (:document_id, :tag_id)"), {"document_id": document_id, "tag_id": tag_id})
    
    if metadata.permissions is not None:
        db.execute(text("DELETE FROM permissions WHERE document_id = :document_id"), {"document_id": document_id})
        for permission in metadata.permissions:
            db.execute(text("INSERT INTO permissions (document_id, user_email) VALUES (:document_id, :user_email)"), {"document_id": document_id, "user_email": permission})
    
    db.commit()
    return {"message": "Metadata updated successfully"}

def delete_document(document_id: str, db: Session):
    document = db.execute(text("SELECT file_path FROM documents WHERE document_id = :document_id"), {"document_id": document_id}).mappings().fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = document["file_path"]
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.execute(text("DELETE FROM documents WHERE document_id = :document_id"), {"document_id": document_id})
    db.commit()
    
    return {"message": "Document deleted successfully"}

def rename_document(document_id: str, current_title: Optional[str], new_title: str, db: Session):
    # Fetch the document
    document = db.execute(
        text("SELECT * FROM documents WHERE document_id = :document_id"),
        {"document_id": document_id}
    ).mappings().fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # If current_title is provided, check if it matches
    if current_title is not None and document["title"] != current_title:
        raise HTTPException(status_code=400, detail="Current title does not match the document's title")

    # Update the title
    db.execute(
        text("UPDATE documents SET title = :new_title WHERE document_id = :document_id"),
        {"new_title": new_title, "document_id": document_id}
    )
    db.commit()
    return {"message": "Document renamed successfully"}