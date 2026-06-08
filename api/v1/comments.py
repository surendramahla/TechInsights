from flask import jsonify, request, url_for
from . import api_v1_bp
from extensions import db
from models import Blog, Comment, CommentLike, User
from api.serializers import APISerializer
from flask_jwt_extended import jwt_required, get_jwt_identity, jwt_required

@api_v1_bp.route('/blogs/<int:blog_id>/comments', methods=['GET'])
def get_blog_comments(blog_id):
    """
    Get Blog Comments
    ---
    tags:
      - Comments
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 15
    responses:
      200:
        description: Returns a paginated list of top-level comments with nested replies
    """
    blog = Blog.query.get_or_404(blog_id)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)

    # Filter top level comments (no parent_id)
    query = Comment.query.filter_by(blog_id=blog.id, parent_id=None).order_by(Comment.date_posted.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get active user identity if authenticated to set 'has_liked'
    current_user = None
    try:
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            current_user = User.query.get(user_id)
    except Exception:
        pass

    serialized_comments = [APISerializer.comment(c, current_user) for c in pagination.items]

    return jsonify({
        "success": True,
        "message": "Comments retrieved successfully.",
        "data": {
            "comments": serialized_comments,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        }
    }), 200

@api_v1_bp.route('/blogs/<int:blog_id>/comments', methods=['POST'])
@jwt_required()
def create_comment(blog_id):
    """
    Create a new Comment or Reply
    ---
    tags:
      - Comments
    security:
      - ApiKeyAuth: []
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
      - in: body
        name: body
        required: True
        schema:
          type: object
          required:
            - content
          properties:
            content:
              type: string
              example: This is a great post, thanks for sharing!
            parent_id:
              type: integer
              description: ID of parent comment (for nested replies)
    responses:
      201:
        description: Comment created successfully
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    blog = Blog.query.get_or_404(blog_id)

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "Comment content cannot be empty."
        }), 400

    content = data['content'].strip()
    parent_id = data.get('parent_id')

    # Validate parent comment exists and belongs to same blog
    if parent_id:
        parent_comment = Comment.query.get(parent_id)
        if not parent_comment or parent_comment.blog_id != blog.id:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "Invalid parent comment ID."
            }), 400

    comment = Comment(
        content=content,
        author=user,
        blog=blog,
        parent_id=parent_id
    )
    db.session.add(comment)
    db.session.commit()

    # Trigger notifications
    if blog.author != user:
        from services.socket_service import send_notification
        send_notification(
            receiver_id=blog.author.id,
            sender_id=user.id,
            notification_type='comment',
            message=f"{user.username} commented on your blog '{blog.title[:20]}...'",
            link_url=url_for('blog_detail', blog_id=blog.id)
        )

    return jsonify({
        "success": True,
        "message": "Comment posted successfully.",
        "data": APISerializer.comment(comment, current_user=user)
    }), 201

@api_v1_bp.route('/comments/<int:comment_id>', methods=['PUT'])
@jwt_required()
def edit_comment(comment_id):
    """
    Edit a Comment
    ---
    tags:
      - Comments
    security:
      - ApiKeyAuth: []
    parameters:
      - name: comment_id
        in: path
        type: integer
        required: True
      - in: body
        name: body
        required: True
        schema:
          type: object
          required:
            - content
          properties:
            content:
              type: string
    responses:
      200:
        description: Comment updated successfully
    """
    comment = Comment.query.get_or_404(comment_id)
    current_user_id = get_jwt_identity()

    if comment.user_id != current_user_id:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "You do not have permission to edit this comment."
        }), 403

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "Comment content cannot be empty."
        }), 400

    comment.content = data['content'].strip()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Comment updated successfully.",
        "data": APISerializer.comment(comment, current_user=comment.author)
    }), 200

@api_v1_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id):
    """
    Delete a Comment
    ---
    tags:
      - Comments
    security:
      - ApiKeyAuth: []
    parameters:
      - name: comment_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Comment deleted successfully
    """
    comment = Comment.query.get_or_404(comment_id)
    current_user_id = get_jwt_identity()

    if comment.user_id != current_user_id and not comment.blog.user_id == current_user_id:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "You do not have permission to delete this comment."
        }), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Comment deleted successfully."
    }), 200

@api_v1_bp.route('/comments/<int:comment_id>/like', methods=['POST'])
@jwt_required()
def like_comment(comment_id):
    """
    Like / Unlike Comment
    ---
    tags:
      - Comments
    security:
      - ApiKeyAuth: []
    parameters:
      - name: comment_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Returns updated comment likes count
    """
    comment = Comment.query.get_or_404(comment_id)
    current_user_id = get_jwt_identity()

    cl = CommentLike.query.filter_by(user_id=current_user_id, comment_id=comment.id).first()
    if cl:
        db.session.delete(cl)
        db.session.commit()
        status = "unliked"
    else:
        db.session.add(CommentLike(user_id=current_user_id, comment_id=comment.id))
        db.session.commit()
        status = "liked"

    return jsonify({
        "success": True,
        "message": f"Comment {status} successfully.",
        "data": {
            "status": status,
            "likes_count": len(comment.comment_likes)
        }
    }), 200
