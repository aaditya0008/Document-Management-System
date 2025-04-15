from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

def create_folder(folder_name: str, created_by: int, db: Session):
    try:
        db.execute(
            text("INSERT INTO folders (folder_name, created_by) VALUES (:folder_name, :created_by)"),
            {"folder_name": folder_name, "created_by": created_by}
        )
        db.commit()
        return {"message": "Folder created successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

def get_all_folders(db: Session):
    folders = db.execute(text("SELECT folder_id, folder_name FROM folders")).mappings().fetchall()
    return folders

def delete_folder(folder_id: int, db: Session):
    try:
        db.execute(text("DELETE FROM folders WHERE folder_id = :folder_id"), {"folder_id": folder_id})
        db.commit()
        return {"message": "Folder deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting folder: {str(e)}")

def rename_folder(folder_id: int, new_name: str, db: Session):
    db.execute(
        text("UPDATE folders SET folder_name = :new_name WHERE folder_id = :folder_id"),
        {"new_name": new_name, "folder_id": folder_id}
    )
    db.commit()
    return {"message": "Folder renamed successfully"}
