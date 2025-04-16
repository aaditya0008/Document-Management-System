# Document Management System

The **Document Management System** is a comprehensive application designed to handle document uploads, text extraction, translation, summarization, search, and more. It leverages FastAPI for backend services and integrates various utilities for efficient document processing.

---

## Features
- **Document Upload**: Upload and manage PDF and DOCX files.
- **Text Extraction**: Extract text from uploaded documents using `pdfminer.six` and `python-docx`.
- **Translation**: Translate extracted text into different languages using the Gemini API.
- **Summarization**: Summarize document content with AI-powered APIs.
- **Search**: Search documents by title, tags, or uploader.
- **Transliteration**: Convert text into different scripts.
- **Image Extraction**: Extract images from PDF and DOCX files.
- **User Authentication**: Secure user registration, login, and OTP verification.
- **Activity Logs**: Track user actions and maintain logs in the database.
- **Comments**: Add comments to documents for collaboration.

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/document-management-system.git
   cd document-management-system
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up the environment variables:
   ```bash
   cp .env.example .env
   ```

4. Run the FastAPI server:
   ```bash
   uvicorn app_fast_api:app --reload
   ```



## Usage

Access the API Documentation: Open your browser and navigate to:

Swagger UI: http://127.0.0.1:8000/docs
ReDoc: http://127.0.0.1:8000/redoc

Document-Management-System/
├── utility/
│   ├── document_upload.py       # Handles document uploads
│   ├── extract_text.py          # Extracts text from documents
│   ├── translate_text.py        # Translates text using Gemini API
│   ├── summarize_text.py        # Summarizes document content
│   ├── transliteration.py       # Handles transliteration of text
│   ├── extract_images.py        # Extracts images from documents
│   ├── search.py                # Implements document search functionality
│   ├── qna.py                   # Question and Answer functionality
│   ├── logs.py                  # Manages activity logs
│   ├── comments.py              # Handles document comments
│   ├── auth.py                  # User authentication and authorization
├── helpers/
│   ├── constants.py             # Application constants
│   ├── database.py              # Database configuration and models
├── [app_fast_api.py](http://_vscodecontentref_/1)              # FastAPI application entry point
├── [app_stream.py](http://_vscodecontentref_/2)                # Streamlit application entry point
├── [requirements.txt](http://_vscodecontentref_/3)             # Project dependencies
├── [README.md](http://_vscodecontentref_/4)                    # Project documentation
└── .env                         # Environment variables
>>>>>>> 37f894c (updated read me file)
