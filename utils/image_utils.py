import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image(file):
    """
    Validate the image file:
    1. Check file extension
    2. Check file size
    Returns (True, None) if valid, (False, error_message) if invalid.
    """
    if not file:
        return False, "No file provided."

    if not allowed_file(file.filename):
        return False, "Invalid file type. Allowed: JPG, PNG, WEBP, JPEG"

    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    if file_length > MAX_FILE_SIZE:
        return False, "File is too large. Maximum size is 5MB."
    
    # Reset file pointer
    file.seek(0)
    
    return True, None
