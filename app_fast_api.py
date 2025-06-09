from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from helpers.database import get_db
from utility.search import search_documents
from utility.documents import (
    upload_document,
    get_document_metadata,
    download_document,
    edit_document_metadata,
    delete_document,
    DocumentMetadata,
    rename_document
)
from utility.auth import register_user, verify_otp, login_user, get_current_user
from utility.view import fetch_all_documents
from utility.logs import fetch_all_logs, ActivityLog, document_logs, user_logs, fetch_logs, add_log_to_db
from utility.comments import add_comment
from typing import List, Literal
from typing import Optional

from utility.summarize_text import summarize_text, extract_text
from utility.translate_text import translate_text, process_text_input
from utility.transliteration import process_file_input, transliterate_text, clean_text
from utility.qna import get_answer, process_file
from utility.extract_text import process_document_upload
from utility.extract_images import extract_images_from_pdf
from utility.folders import create_folder, delete_folder, get_all_folders, rename_folder
app = FastAPI(title="AI Document Processor and Management API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Search API
@app.get("/documents/search")
def search_endpoint(
    query: Optional[str] = None,  # Unified search query
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Search query cannot be empty.")

        # Query to fetch documents based on tags, title, uploaded_by, or document_id
        sql_query = """
        SELECT DISTINCT d.document_id, d.title, u.email AS uploaded_by, f.folder_id, f.folder_name,
                        GROUP_CONCAT(t.tag_name) AS tags, GROUP_CONCAT(p.user_email) AS permissions
        FROM documents d
        LEFT JOIN document_tags dt ON d.document_id = dt.document_id
        LEFT JOIN tags t ON dt.tag_id = t.tag_id
        LEFT JOIN permissions p ON d.document_id = p.document_id
        LEFT JOIN folders f ON d.folder_id = f.folder_id
        JOIN users u ON d.uploaded_by = u.id
        WHERE LOWER(d.title) LIKE LOWER(:query)
           OR LOWER(t.tag_name) LIKE LOWER(:query)
           OR LOWER(u.email) LIKE LOWER(:query)
           OR LOWER(d.document_id) LIKE LOWER(:query)
        GROUP BY d.document_id, d.title, u.email, f.folder_id, f.folder_name
        """

        # Execute the query
        documents = db.execute(text(sql_query), {"query": f"%{query}%"}).mappings().all()

        return {"documents": documents} if documents else {"message": "No documents found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ✅ Upload Document API
@app.post("/documents/upload")
def upload_endpoint(
    file: UploadFile = File(...),
    title: str = Form(...),
    tags: List[str] = Form(...),
    permissions: List[str] = Form(...),
    uploaded_by: int = Form(...),
    folder_name: Optional[str] = Form(None),  # Add folder_name as an optional parameter
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Check if folder_name is provided
    folder_id = None
    if folder_name:
        # Fetch the folder ID based on the folder name
        folder = db.execute(
            text("SELECT folder_id FROM folders WHERE folder_name = :folder_name"),
            {"folder_name": folder_name}
        ).mappings().fetchone()  # Use .mappings() to return a dictionary-like result

        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        folder_id = folder["folder_id"]  # Access folder_id as a dictionary key

    # Pass folder_id to the upload_document function
    return upload_document(file, title, tags, permissions, uploaded_by, db, folder_id)

# ✅ Get Document Metadata API
@app.get("/documents/{document_id}")
def get_metadata_endpoint(document_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Fetch document metadata along with folder name
    document = db.execute(
        text("""
            SELECT d.*, f.folder_name
            FROM documents d
            LEFT JOIN folders f ON d.folder_id = f.folder_id
            WHERE d.document_id = :document_id
        """),
        {"document_id": document_id}
    ).mappings().fetchone()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch tags
    tags = db.execute(
        text("""
            SELECT t.tag_name
            FROM tags t
            JOIN document_tags dt ON t.tag_id = dt.tag_id
            WHERE dt.document_id = :document_id
        """),
        {"document_id": document_id}
    ).mappings().fetchall()

    # Fetch permissions
    permissions = db.execute(
        text("""
            SELECT user_email
            FROM permissions
            WHERE document_id = :document_id
        """),
        {"document_id": document_id}
    ).mappings().fetchall()

    # Prepare the response
    return {
        "document_id": document["document_id"],
        "title": document["title"],
        "folder_name": document["folder_name"],  # Include folder name
        "tags": [tag["tag_name"] for tag in tags],
        "uploaded_by": document["uploaded_by"],
        "permissions": [permission["user_email"] for permission in permissions],
        "last_updated": document["last_updated"]
    }

# ✅ Download Document API
@app.get("/documents/download/{document_id}")
def download_endpoint(document_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return download_document(document_id, db)

# ✅ Edit Document Metadata API
@app.put("/documents/edit/{document_id}")
def edit_metadata_endpoint(document_id: str, metadata: DocumentMetadata, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return edit_document_metadata(document_id, metadata, db)

# ✅ Delete Document API
@app.delete("/documents/delete/{document_id}")
def delete_endpoint(document_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return delete_document(document_id, db)

# ✅ Fetch All Documents API
@app.get("/documents", summary="View/File Explorer")
def get_all_documents(db: Session = Depends(get_db)):
    """
    Endpoint to fetch all documents along with their metadata, tags, and comments.
    """
    try:
        documents = fetch_all_documents(db)
        return JSONResponse(content={"documents": documents}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"detail": str(e)}, status_code=500)

# ✅ User Registration Endpoint
@app.post("/auth/register")
async def register_user_endpoint(
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    return register_user(db, email)

# ✅ Verify OTP Endpoint
@app.post("/auth/verify-otp")
async def verify_otp_endpoint(
    email: str = Form(...),
    otp: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    role: Literal["editor", "viewer", "admin"] = Form(...),
    db: Session = Depends(get_db)
):
    return verify_otp(db, email, otp, username, password, role)

# ✅ User Login Endpoint
@app.post("/auth/login")
async def login_user_endpoint(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    return login_user(db, email, password)

# ✅ Fetch User Logs Endpoint (uses document_name now)
''''@app.get("/logs/user/{user_id}", response_model=List[ActivityLog])
async def get_user_logs(user_id: int, db: Session = Depends(get_db)):
    try:
        logs = fetch_logs(db, user_id)
        if not logs:
            raise HTTPException(status_code=404, detail=f"No logs found for user ID {user_id}")
        return logs
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")'''

# ✅ Add Log Endpoint (uses document_name now)
@app.post("/logs/user/{user_id}")
async def add_log(user_id: int, log: ActivityLog, db: Session = Depends(get_db)):
    return add_log_to_db(db, user_id, log)

# ✅ Fetch All Logs Endpoint (uses document_name now)
@app.get("/logs/all")
async def get_all_logs(db: Session = Depends(get_db)):
    return {"logs": fetch_all_logs(db)}

# ✅ Fetch Document Logs Endpoint
@app.get("/logs/documents")
async def get_document_logs(db: Session = Depends(get_db)):
    try:
        logs = document_logs(db)
        return {"logs": logs}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# ✅ Fetch User Logs Endpoint
@app.get("/logs/users")
async def get_user_logs(db: Session = Depends(get_db)):
    try:
        logs = user_logs(db)
        return {"logs": logs}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# ✅ Add Comment Endpoint
@app.post("/comments")
async def add_comment_endpoint(
    document_id: str,
    user_email: str,
    comment_text: str,
    db: Session = Depends(get_db)
):
    return add_comment(db, document_id, user_email, comment_text)

# ✅ Extract Text Endpoint
@app.post("/extract-text/")
async def extract_text_endpoint(file: UploadFile = File(...)):
    try:
        extracted_text = process_document_upload(file)
        return {"extracted_text": extracted_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Extract Images from PDF Endpoint
@app.post("/extract-images/")
async def extract_images_endpoint(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if file.filename.endswith(".pdf"):
            images = extract_images_from_pdf(contents)
            return {"images": images}
        else:
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Translate Endpoint
@app.post("/translate/")
async def translate_endpoint(
    file: UploadFile = File(None),
    text: str = Form(None),
    target_language: str = Form(...),
    file_upload: bool = Form(...)
):
    extracted_text_list = process_text_input(file, text, file_upload)
    final_translation = translate_text(extracted_text_list, target_language)
    return {"translated_text": final_translation}

# ✅ Transliterate Endpoint
@app.post("/transliterate/")
async def transliterate_endpoint(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    target_script: str = Form(...),
    file_upload: bool = Form(...)
):
    extracted_text = process_file_input(file) if file_upload and file else text

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(status_code=400, detail="No text found to transliterate")

    result = transliterate_text(clean_text(extracted_text), target_script)
    return {"transliterated_text": result}

# ✅ QnA Endpoint
@app.post("/qna", summary="Question & Answer")
async def ask_question(
    file: UploadFile = File(..., description="Upload a PDF or DOCX file"),
    question: str = Form(..., description="Enter your question")
):
    """Handles Q&A processing based on uploaded PDF or DOCX."""
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
   
    context = process_file(file)
    if not context:
        raise HTTPException(status_code=400, detail="No extractable text found in the document.")
   
    answer = get_answer(question, context)
    return {"question": question, "answer": answer, "file": file.filename}

# ✅ Summarization Endpoint
@app.post("/summarize-text/")
async def summarize_text_endpoint(file: UploadFile = File(...)):
    """Handles file upload and calls summarization function."""
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or DOCX files only.")
   
    text = extract_text(file)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the file.")
   
    summary = summarize_text(text)
    return {"summary": summary}

# ✅ Change Role API
@app.put("/auth/change-role")
async def change_role_endpoint(
    email: str = Form(..., description="Email of the user whose role is to be changed"),
    new_role: str = Form(..., description="New role to assign (admin, editor, viewer)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    from utility.role_manager import change_user_role
    user_id = db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": current_user["email"]}
    ).fetchone()
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")
    return change_user_role(email, new_role, db, current_user)

#folder endpoints

@app.post("/folders/create")
def create_folder_endpoint(folder_name: str = Form(...), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    print(user)  # Debugging
    if "id" not in user:
        raise HTTPException(status_code=400, detail="User ID not found in the request")
    return create_folder(folder_name, user["id"], db)

@app.delete("/folders/delete/{folder_id}")
def delete_folder_endpoint(folder_id: int, db: Session = Depends(get_db)):
    return delete_folder(folder_id, db)  # Ensure the correct order of arguments

@app.put("/folders/rename/{folder_id}")
def rename_folder_endpoint(folder_id: int, new_name: str = Form(...), db: Session = Depends(get_db)):
    return rename_folder(folder_id, new_name, db)

@app.get("/folders")
def get_folders_endpoint(db: Session = Depends(get_db)):
    return get_all_folders(db)

@app.post("/folders/{folder_name}/upload")
def upload_file_to_folder(
    folder_name: str,  # Folder name fetched automatically from the URL
    file: UploadFile = File(...),  # File to upload
    tags: Optional[List[str]] = Form(None),  # Tags for the document (optional)
    db: Session = Depends(get_db),  # Database session
    user: dict = Depends(get_current_user)  # Current user
):
    """
    Upload a file to a specific folder.
    The folder name is fetched automatically from the URL.
    """
    # Extract the original file name
    original_file_name = file.filename

    # Get the user ID from the current user
    uploaded_by = user["id"]

    # Fetch the folder ID based on the folder name
    folder = db.execute(
        text("SELECT folder_id FROM folders WHERE folder_name = :folder_name"),
        {"folder_name": folder_name}
    ).mappings().fetchone()

    if not folder:
        raise HTTPException(status_code=404, detail=f"Folder '{folder_name}' not found")

    folder_id = folder["folder_id"]  # Access folder_id as a dictionary key

    # Pass the extracted details to the `upload_document` function
    return upload_document(
        file=file,
        title=original_file_name,  # Use the original file name as the title
        tags=tags or [],  # Handle empty tags by passing an empty list
        permissions=[],  # No permissions provided in this case
        uploaded_by=uploaded_by,
        db=db,
        folder_id=folder_id
    )

@app.get("/folders/{folder_id}/documents", summary="Get Folder Details and Documents")
def get_folder_documents(
    folder_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Fetch the folder name, folder ID, and all document names inside the folder.
    """
    # Fetch folder details
    folder = db.execute(
        text("SELECT folder_id, folder_name FROM folders WHERE folder_id = :folder_id"),
        {"folder_id": folder_id}
    ).mappings().fetchone()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Fetch documents inside the folder
    documents = db.execute(
        text("SELECT title FROM documents WHERE folder_id = :folder_id"),
        {"folder_id": folder_id}
    ).mappings().fetchall()

    # Prepare the response
    return {
        "folder_id": folder["folder_id"],
        "folder_name": folder["folder_name"],
        "documents": [doc["title"] for doc in documents]
    }

@app.get("/folders/all-documents", summary="Get All Folders and Their Documents")
def get_all_folders_and_documents(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Fetch all folders with their names, IDs, and the names of all documents inside each folder.
    """
    # Fetch all folders
    folders = db.execute(
        text("SELECT folder_id, folder_name FROM folders")
    ).mappings().fetchall()

    if not folders:
        raise HTTPException(status_code=404, detail="No folders found")

    # Prepare the response
    response = []
    for folder in folders:
        # Fetch documents inside the folder
        documents = db.execute(
            text("SELECT title FROM documents WHERE folder_id = :folder_id"),
            {"folder_id": folder["folder_id"]}
        ).mappings().fetchall()

        # Append folder details and document names to the response
        response.append({
            "folder_name": folder["folder_name"],
            "folder_id": folder["folder_id"],
            "files": [doc["title"] for doc in documents]
        })

    return response

# ✅ Main entry point (fixed)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/auth/get-role", summary="Get Current User Role")
def get_user_role_endpoint(
    current_user: dict = Depends(get_current_user)  # Fetch the current user using the existing function
):
    """
    Endpoint to fetch the role of the currently logged-in user.
    """
    return {"role": current_user["role"]}

@app.get("/auth/get-user-info", summary="Get Current User Info")
def get_user_info_endpoint(
    current_user: dict = Depends(get_current_user)  # Fetch the current user using the existing function
):
    """
    Endpoint to fetch the current user's ID, username, and email.
    """
    return {
        "user_id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"]
    }

@app.put("/documents/rename/{document_id}", summary="Rename a document")
def rename_document_endpoint(
    document_id: str,
    current_title: Optional[str] = Form(None),
    new_title: str = Form(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    from utility.documents import rename_document
    return rename_document(document_id, current_title, new_title, db)