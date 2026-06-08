from flask import jsonify, request
from . import api_v1_bp
from extensions import db
from models import User
from services.cloudinary_service import upload_image, delete_image
from utils.image_utils import validate_image
from flask_jwt_extended import jwt_required, get_jwt_identity

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS

@api_v1_bp.route('/upload/blog-image', methods=['POST'])
@jwt_required()
def upload_blog_image():
    """
    Upload Blog Cover or Inline Image
    ---
    tags:
      - Media Uploads
    security:
      - ApiKeyAuth: []
    parameters:
      - name: image
        in: formData
        type: file
        required: True
        description: The image file to upload (PNG, JPG, JPEG, GIF, WEBP)
    responses:
      200:
        description: Image uploaded successfully to Cloudinary, returns secure URL
      400:
        description: Missing file or file type not allowed
    """
    if 'image' not in request.files:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "No file stream provided with key 'image'."
        }), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "No file selected."
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": f"Allowed extensions are: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    # Perform optional image dimensions validation using existing utility
    # (Since validate_image may check sizes)
    # Upload to Cloudinary under the 'techinsights/covers' folder
    result = upload_image(file, folder="techinsights/covers")
    if not result:
        return jsonify({
            "success": False,
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Failed to upload image to Cloudinary storage server."
        }), 500

    return jsonify({
        "success": True,
        "message": "Blog image uploaded successfully.",
        "data": {
            "url": result['url'],
            "public_id": result['public_id'],
            "format": result['format'],
            "bytes_size": result['size']
        }
    }), 200

@api_v1_bp.route('/upload/profile-image', methods=['POST'])
@jwt_required()
def upload_profile_image():
    """
    Upload and Update User Profile Picture
    ---
    tags:
      - Media Uploads
    security:
      - ApiKeyAuth: []
    parameters:
      - name: image
        in: formData
        type: file
        required: True
        description: The profile picture file
    responses:
      200:
        description: Profile picture uploaded successfully and updated on User model
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "User session not active."
        }), 401

    if 'image' not in request.files:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "No file stream provided with key 'image'."
        }), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "No file selected."
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": f"Allowed extensions are: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    # Delete old profile picture if exists in Cloudinary
    if user.profile_image_public_id:
        delete_image(user.profile_image_public_id)

    # Upload to Cloudinary under the 'techinsights/profiles' folder
    result = upload_image(file, folder="techinsights/profiles")
    if not result:
        return jsonify({
            "success": False,
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Failed to upload profile picture to Cloudinary storage server."
        }), 500

    # Update User model
    user.image_file = result['url']
    user.profile_image_public_id = result['public_id']
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Profile picture updated successfully.",
        "data": {
            "image_url": user.image_file,
            "public_id": user.profile_image_public_id
        }
    }), 200
