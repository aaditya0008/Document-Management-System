-- Ensure the database exists
CREATE DATABASE IF NOT EXISTS document_db;
USE document_db;

-- USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL DEFAULT 'user'
);

-- DOCUMENTS TABLE
CREATE TABLE IF NOT EXISTS documents (
    document_id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    uploaded_by INT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
);

-- TAGS TABLE
CREATE TABLE IF NOT EXISTS tags (
    tag_id INT AUTO_INCREMENT PRIMARY KEY,
    tag_name VARCHAR(255) UNIQUE
);

-- DOCUMENT_TAGS TABLE
CREATE TABLE IF NOT EXISTS document_tags (
    document_id VARCHAR(36),
    tag_id INT,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

-- PERMISSIONS TABLE
CREATE TABLE IF NOT EXISTS permissions (
    permission_id INT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(36),
    user_email VARCHAR(255) NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

-- ACTIVITY LOGS TABLE
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(255) NOT NULL,
    document_id VARCHAR(36),
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE SET NULL
);

-- COMMENTS TABLE
CREATE TABLE IF NOT EXISTS comments (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    comment_text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE
);

-- OTP VERIFICATION TABLE
CREATE TABLE IF NOT EXISTS otp_verification (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    otp VARCHAR(6) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TRIGGERS

DELIMITER $$

-- Log document deletion
CREATE TRIGGER IF NOT EXISTS log_document_deletion
BEFORE DELETE ON documents
FOR EACH ROW
BEGIN
    INSERT INTO activity_logs (user_id, action, document_id, timestamp)
    VALUES (OLD.uploaded_by, 'Deleted document', OLD.document_id, NOW());
END$$

-- Log document upload
CREATE TRIGGER IF NOT EXISTS log_document_insert
AFTER INSERT ON documents
FOR EACH ROW
BEGIN
    INSERT INTO activity_logs (user_id, action, document_id, timestamp)
    VALUES (NEW.uploaded_by, 'Uploaded document', NEW.document_id, NOW());
END$$

-- Log metadata updates
CREATE TRIGGER IF NOT EXISTS log_document_update
BEFORE UPDATE ON documents
FOR EACH ROW
BEGIN
    IF OLD.title <> NEW.title OR OLD.file_path <> NEW.file_path THEN
        INSERT INTO activity_logs (user_id, action, document_id, timestamp)
        VALUES (OLD.uploaded_by, 'Updated document metadata', OLD.document_id, NOW());
    END IF;
END$$

-- Log comment insert
CREATE TRIGGER IF NOT EXISTS log_comment_insert
AFTER INSERT ON comments
FOR EACH ROW
BEGIN
    INSERT INTO activity_logs (user_id, action, document_id, timestamp)
    VALUES (
        (SELECT id FROM users WHERE email = NEW.user_email),
        'Added comment',
        NEW.document_id,
        NOW()
    );
END$$

DELIMITER ;

-- Optional cleanup (dev-only)
-- SET SQL_SAFE_UPDATES = 0;
-- DELETE FROM otp_verification WHERE id <> 5;
-- FOLDERS TABLE
CREATE TABLE IF NOT EXISTS folders (
    folder_id INT AUTO_INCREMENT PRIMARY KEY,
    folder_name VARCHAR(255) NOT NULL,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- ALTER DOCUMENTS TABLE to link with folders
ALTER TABLE documents ADD COLUMN folder_id INT;

-- Add foreign key relationship
ALTER TABLE documents
ADD CONSTRAINT fk_folder
FOREIGN KEY (folder_id) REFERENCES folders(folder_id) ON DELETE SET NULL;
