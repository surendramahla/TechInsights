from flask import jsonify, request, url_for
from . import api_v1_bp
from extensions import db, limiter
from models import Blog, Category, Tag, User
from api.serializers import APISerializer
from flask_jwt_extended import jwt_required, get_jwt_identity
import bleach
import re

@api_v1_bp.route('/blogs', methods=['GET'])
@limiter.limit("100 per minute")
def get_blogs():
    """
    List Blog Posts API
    ---
    tags:
      - Blogs
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: Page number
      - name: per_page
        in: query
        type: integer
        default: 10
        description: Number of blogs per page
      - name: q
        in: query
        type: string
        description: Search term matching title or content
      - name: cat_id
        in: query
        type: integer
        description: Filter blogs by Category ID
      - name: tag
        in: query
        type: string
        description: Filter blogs by Tag Name
      - name: sort
        in: query
        type: string
        enum: [newest, popular]
        default: newest
        description: Sorting method
      - name: featured
        in: query
        type: boolean
        description: Filter featured blogs only
      - name: trending
        in: query
        type: boolean
        description: Filter top trending blogs
    responses:
      200:
        description: Returns a paginated list of blog articles
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('q', '').strip()
    category_id = request.args.get('cat_id', type=int)
    tag_name = request.args.get('tag', '').strip()
    sort_by = request.args.get('sort', 'newest')
    featured = request.args.get('featured', '').lower() == 'true'
    trending = request.args.get('trending', '').lower() == 'true'

    from sqlalchemy.orm import joinedload
    query = Blog.query.options(
        joinedload(Blog.author),
        joinedload(Blog.category)
    ).filter_by(is_blocked=False)

    # Search filter
    if search_query:
        query = query.filter(
            Blog.title.contains(search_query) | Blog.content.contains(search_query)
        )

    # Category filter
    if category_id:
        query = query.filter_by(category_id=category_id)

    # Tag filter
    if tag_name:
        query = query.join(Blog.tags).filter(Tag.name == tag_name.lower())

    # Featured filter
    if featured:
        query = query.filter_by(is_featured=True)

    # Sorting
    if trending or sort_by == 'popular':
        query = query.order_by(Blog.views.desc())
    else:
        query = query.order_by(Blog.date_posted.desc())

    # Limit to top 5 if trending is requested without explicit pagination
    if trending and not request.args.get('page'):
        blogs = query.limit(5).all()
        return jsonify({
            "success": True,
            "message": "Trending blogs retrieved successfully.",
            "data": [APISerializer.blog(b, include_content=False) for b in blogs]
        }), 200

    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    serialized_blogs = [APISerializer.blog(b, include_content=False) for b in pagination.items]

    return jsonify({
        "success": True,
        "message": "Blogs retrieved successfully.",
        "data": {
            "blogs": serialized_blogs,
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

@api_v1_bp.route('/blogs/<int:blog_id>', methods=['GET'])
def get_blog_detail(blog_id):
    """
    Get Blog Post Details
    ---
    tags:
      - Blogs
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
        description: ID of the blog article
    responses:
      200:
        description: Returns full blog details and increments view count
      404:
        description: Blog post not found
    """
    blog = Blog.query.get_or_404(blog_id)
    if blog.is_blocked:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "This article has been blocked by system administrators."
        }), 403

    # Increment view counter securely
    blog.views += 1
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Blog detail retrieved successfully.",
        "data": APISerializer.blog(blog, include_content=True)
    }), 200

@api_v1_bp.route('/blogs', methods=['POST'])
@jwt_required()
def create_blog():
    """
    Create a new Blog Post
    ---
    tags:
      - Blogs
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        required: True
        schema:
          type: object
          required:
            - title
            - content
          properties:
            title:
              type: string
              example: Getting Started with Docker and Flask
            content:
              type: string
              example: "<p>This is standard Quill HTML rich content...</p>"
            category_id:
              type: integer
              example: 1
            tags:
              type: string
              example: "docker, devops, flask, scalability"
            cover_image:
              type: string
              example: "https://res.cloudinary.com/..."
    responses:
      201:
        description: Blog post published successfully
      400:
        description: Missing required fields
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "User session not active."
        }), 401

    data = request.get_json()
    if not data or not data.get('title') or not data.get('content'):
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "Missing required fields: title, content."
        }), 400

    title = data['title'].strip()
    # Sanitize content using bleach to protect against XSS
    from app import sanitize_html
    content = sanitize_html(data['content'])

    category_id = data.get('category_id')
    if category_id:
        Category.query.get_or_404(category_id)

    # Process AI sentiment analysis
    from services.ai_service import analyze_sentiment
    sentiment = analyze_sentiment(content)

    blog = Blog(
        title=title,
        content=content,
        author=user,
        category_id=category_id,
        sentiment=sentiment
    )

    if data.get('cover_image'):
        blog.cover_image = data['cover_image'].strip()

    # AI Tag fallback generation if empty
    tag_string = data.get('tags', '').strip()
    if not tag_string:
        from services.ai_service import generate_tags
        ai_tags = generate_tags(content, num_tags=5)
        tag_string = ', '.join(ai_tags)

    # Process and append tags
    from app import process_tags
    blog.tags = process_tags(tag_string)

    db.session.add(blog)
    db.session.commit()
    from extensions import cache
    cache.delete('api_stats')

    return jsonify({
        "success": True,
        "message": "Blog post created and published successfully.",
        "data": APISerializer.blog(blog, include_content=True)
    }), 201

@api_v1_bp.route('/blogs/<int:blog_id>', methods=['PUT'])
@jwt_required()
def update_blog(blog_id):
    """
    Update Blog Post details
    ---
    tags:
      - Blogs
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
          properties:
            title:
              type: string
            content:
              type: string
            category_id:
              type: integer
            tags:
              type: string
            cover_image:
              type: string
    responses:
      200:
        description: Blog post updated successfully
      403:
        description: Unauthorized (only author or admin allowed)
    """
    blog = Blog.query.get_or_404(blog_id)
    current_user_id = get_jwt_identity()

    if blog.user_id != current_user_id:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "You do not have permission to edit this article."
        }), 403

    data = request.get_json()
    if not data:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "No update fields provided."
        }), 400

    if data.get('title'):
        blog.title = data['title'].strip()

    if data.get('content'):
        from app import sanitize_html
        blog.content = sanitize_html(data['content'])

    if 'category_id' in data:
        cat_id = data['category_id']
        if cat_id:
            Category.query.get_or_404(cat_id)
        blog.category_id = cat_id

    if 'tags' in data:
        from app import process_tags
        blog.tags = process_tags(data['tags'])

    if data.get('cover_image'):
        blog.cover_image = data['cover_image'].strip()

    db.session.commit()
    from extensions import cache
    cache.delete('api_stats')

    return jsonify({
        "success": True,
        "message": "Blog post updated successfully.",
        "data": APISerializer.blog(blog, include_content=True)
    }), 200

@api_v1_bp.route('/blogs/<int:blog_id>', methods=['DELETE'])
@jwt_required()
def delete_blog(blog_id):
    """
    Delete a Blog Post
    ---
    tags:
      - Blogs
    security:
      - ApiKeyAuth: []
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Blog post deleted successfully
      403:
        description: Unauthorized
    """
    blog = Blog.query.get_or_404(blog_id)
    current_user_id = get_jwt_identity()

    if blog.user_id != current_user_id:
        return jsonify({
            "success": False,
            "error": "FORBIDDEN",
            "message": "You do not have permission to delete this article."
        }), 403

    # Handle Cloudinary clean up if image public ID is saved
    if blog.image_public_id:
        from services.cloudinary_service import delete_image
        delete_image(blog.image_public_id)

    db.session.delete(blog)
    db.session.commit()
    from extensions import cache
    cache.delete('api_stats')

    return jsonify({
        "success": True,
        "message": "Blog post deleted successfully."
    }), 200

@api_v1_bp.route('/blogs/<int:blog_id>/like', methods=['POST'])
@jwt_required()
def like_blog(blog_id):
    """
    Like a Blog Post
    ---
    tags:
      - Blogs
    security:
      - ApiKeyAuth: []
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Blog liked successfully, returns updated likes count
      400:
        description: Already liked
    """
    blog = Blog.query.get_or_404(blog_id)
    current_user_id = get_jwt_identity()
    from models import Like, User
    
    like = Like.query.filter_by(user_id=current_user_id, blog_id=blog.id).first()
    if like:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You have already liked this blog article."
        }), 400
        
    db.session.add(Like(user_id=current_user_id, blog_id=blog.id))
    db.session.commit()
    
    # Trigger notifications
    if blog.author.id != current_user_id:
        user = User.query.get(current_user_id)
        from services.socket_service import send_notification
        send_notification(
            receiver_id=blog.author.id,
            sender_id=current_user_id,
            notification_type='like',
            message=f"{user.username} liked your blog '{blog.title[:20]}...'",
            link_url=url_for('blog_detail', blog_id=blog.id)
        )
        
    return jsonify({
        "success": True,
        "message": "Blog liked successfully.",
        "data": {
            "status": "liked",
            "likes_count": len(blog.likes)
        }
    }), 200

@api_v1_bp.route('/blogs/<int:blog_id>/like', methods=['DELETE'])
@jwt_required()
def unlike_blog(blog_id):
    """
    Unlike a Blog Post
    ---
    tags:
      - Blogs
    security:
      - ApiKeyAuth: []
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Blog unliked successfully, returns updated likes count
      400:
        description: Not liked yet
    """
    blog = Blog.query.get_or_404(blog_id)
    current_user_id = get_jwt_identity()
    from models import Like
    
    like = Like.query.filter_by(user_id=current_user_id, blog_id=blog.id).first()
    if not like:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You have not liked this blog article yet."
        }), 400
        
    db.session.delete(like)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Blog unliked successfully.",
        "data": {
            "status": "unliked",
            "likes_count": len(blog.likes)
        }
    }), 200

@api_v1_bp.route('/blogs/<int:blog_id>/bookmark', methods=['POST'])
@jwt_required()
def bookmark_blog(blog_id):
    """
    Bookmark a Blog Post
    ---
    tags:
      - Blogs
    security:
      - ApiKeyAuth: []
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Blog bookmarked successfully
      400:
        description: Already bookmarked
    """
    blog = Blog.query.get_or_404(blog_id)
    current_user_id = get_jwt_identity()
    from models import Bookmark, User
    
    bookmark = Bookmark.query.filter_by(user_id=current_user_id, blog_id=blog.id).first()
    if bookmark:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You have already bookmarked this blog article."
        }), 400
        
    db.session.add(Bookmark(user_id=current_user_id, blog_id=blog.id))
    db.session.commit()
    
    # Trigger notifications
    if blog.author.id != current_user_id:
        user = User.query.get(current_user_id)
        from services.socket_service import send_notification
        send_notification(
            receiver_id=blog.author.id,
            sender_id=current_user_id,
            notification_type='bookmark',
            message=f"{user.username} bookmarked your blog '{blog.title[:20]}...'",
            link_url=url_for('blog_detail', blog_id=blog.id)
        )
        
    return jsonify({
        "success": True,
        "message": "Blog bookmarked successfully.",
        "data": {
            "status": "bookmarked"
        }
    }), 200

@api_v1_bp.route('/blogs/<int:blog_id>/bookmark', methods=['DELETE'])
@jwt_required()
def unbookmark_blog(blog_id):
    """
    Unbookmark a Blog Post
    ---
    tags:
      - Blogs
    security:
      - ApiKeyAuth: []
    parameters:
      - name: blog_id
        in: path
        type: integer
        required: True
    responses:
      200:
        description: Blog unbookmarked successfully
      400:
        description: Not bookmarked yet
    """
    blog = Blog.query.get_or_404(blog_id)
    current_user_id = get_jwt_identity()
    from models import Bookmark
    
    bookmark = Bookmark.query.filter_by(user_id=current_user_id, blog_id=blog.id).first()
    if not bookmark:
        return jsonify({
            "success": False,
            "error": "BAD_REQUEST",
            "message": "You have not bookmarked this blog article yet."
        }), 400
        
    db.session.delete(bookmark)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Blog unbookmarked successfully.",
        "data": {
            "status": "unbookmarked"
        }
    }), 200

