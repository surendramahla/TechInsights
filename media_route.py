from flask import Blueprint, request, jsonify, render_template, abort
from flask_login import login_required, current_user
from extensions import db
from models import Media, Blog, User
from services.cloudinary_service import upload_image, delete_image
from utils.image_utils import validate_image

media_bp = Blueprint('media', __name__, url_prefix='/media')

@media_bp.route('/upload', methods=['POST'])
@login_required
def upload_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    is_valid, error_msg = validate_image(file)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    upload_result = upload_image(file)
    if not upload_result:
        return jsonify({'error': 'Cloudinary upload failed'}), 500

    # Save to media model
    media = Media(
        file_name=file.filename,
        file_url=upload_result['url'],
        public_id=upload_result['public_id'],
        user_id=current_user.id
    )
    db.session.add(media)
    db.session.commit()

    return jsonify({
        'message': 'Upload successful',
        'id': media.id,
        'url': upload_result['url'],
        'public_id': upload_result['public_id']
    }), 200


@media_bp.route('/manager', methods=['GET'])
@login_required
def media_manager():
    # Only show current user's media, or all if admin
    if current_user.is_admin:
        media_items = Media.query.order_by(Media.upload_date.desc()).all()
    else:
        media_items = Media.query.filter_by(user_id=current_user.id).order_by(Media.upload_date.desc()).all()
        
    return render_template('media_manager.html', title='Media Management', media_items=media_items)


@media_bp.route('/delete/<int:media_id>', methods=['POST'])
@login_required
def delete_media_item(media_id):
    media = Media.query.get_or_404(media_id)
    if media.user_id != current_user.id and not current_user.is_admin:
        abort(403)
        
    if delete_image(media.public_id):
        db.session.delete(media)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Failed to delete from Cloudinary'}), 500
