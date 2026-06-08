import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename

def init_cloudinary(app):
    """Initialize Cloudinary with credentials from app config or environment variables."""
    cloudinary.config(
        cloud_name=app.config.get('CLOUDINARY_CLOUD_NAME') or os.getenv('CLOUDINARY_CLOUD_NAME') or 'dkwffngtx',
        api_key=app.config.get('CLOUDINARY_API_KEY') or os.getenv('CLOUDINARY_API_KEY') or '428346857834513',
        api_secret=app.config.get('CLOUDINARY_API_SECRET') or os.getenv('CLOUDINARY_API_SECRET') or 'i4GTgH3JTImxPpGknVCH-7G3L00'
    )

def upload_image(file_stream, folder="techinsights/media"):
    """
    Upload an image to Cloudinary.
    Returns a dictionary with 'url' and 'public_id'.
    """
    try:
        response = cloudinary.uploader.upload(
            file_stream,
            folder=folder,
            resource_type="image"
        )
        return {
            "url": response.get("secure_url"),
            "public_id": response.get("public_id"),
            "format": response.get("format"),
            "size": response.get("bytes")
        }
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        return None

def delete_image(public_id):
    """
    Delete an image from Cloudinary by its public_id.
    """
    if not public_id:
        return False
    try:
        response = cloudinary.uploader.destroy(public_id)
        return response.get('result') == 'ok'
    except Exception as e:
        print(f"Cloudinary delete failed: {e}")
        return False
