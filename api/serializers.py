from flask import url_for

class APISerializer:
    """Centralized, high-performance static serializers for TechInsights models."""

    @staticmethod
    def user_basic(user):
        """Minimal user serialization (useful for nested author details)."""
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "image_file": user.image_file,
            "is_verified": user.is_verified
        }

    @staticmethod
    def user_profile(user, current_user=None):
        """Full user serialization with public profile, activity metrics, and follow status."""
        if not user:
            return None
        
        # Calculate relationship stats
        followers_count = user.followers.count()
        following_count = user.followed.count()
        total_blogs = len(user.blogs)
        total_likes = user.total_likes_received()

        profile_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "image_file": user.image_file,
            "bio": user.bio,
            "is_admin": user.is_admin,
            "is_verified": user.is_verified,
            "account_status": user.account_status,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "stats": {
                "followers_count": followers_count,
                "following_count": following_count,
                "total_blogs": total_blogs,
                "total_likes_received": total_likes
            }
        }

        if current_user and current_user.is_authenticated:
            profile_data["is_following"] = current_user.is_following(user)

        return profile_data

    @staticmethod
    def category(category):
        """Category serialization."""
        if not category:
            return None
        return {
            "id": category.id,
            "name": category.name,
            "slug": category.slug
        }

    @staticmethod
    def tag(tag):
        """Tag serialization."""
        if not tag:
            return None
        return {
            "id": tag.id,
            "name": tag.name
        }

    @staticmethod
    def blog(blog, include_content=True):
        """Comprehensive blog post serialization."""
        if not blog:
            return None

        # Build basic structure
        blog_data = {
            "id": blog.id,
            "title": blog.title,
            "slug": blog.slug,
            "date_posted": blog.date_posted.isoformat() if blog.date_posted else None,
            "cover_image": blog.cover_image,
            "excerpt": blog.excerpt(200),
            "views": blog.views,
            "read_time_minutes": blog.read_time(),
            "sentiment": blog.sentiment,
            "summary": blog.summary,
            "is_blocked": blog.is_blocked,
            "is_featured": blog.is_featured,
            "likes_count": len(blog.likes),
            "comments_count": len(blog.comments),
            
            # Nested relations
            "author": APISerializer.user_basic(blog.author),
            "category": APISerializer.category(blog.category),
            "tags": [APISerializer.tag(t) for t in blog.tags]
        }

        if include_content:
            blog_data["content"] = blog.content

        return blog_data

    @staticmethod
    def comment(comment, current_user=None):
        """Advanced comment serialization supporting nested replies & likes check."""
        if not comment:
            return None

        has_liked = False
        if current_user and current_user.is_authenticated:
            from models import CommentLike
            has_liked = CommentLike.query.filter_by(
                user_id=current_user.id, comment_id=comment.id).first() is not None

        return {
            "id": comment.id,
            "content": comment.content,
            "date_posted": comment.date_posted.isoformat() if comment.date_posted else None,
            "parent_id": comment.parent_id,
            "is_reported": comment.is_reported,
            "likes_count": len(comment.comment_likes),
            "has_liked": has_liked,
            
            # Relations
            "author": APISerializer.user_basic(comment.author),
            
            # Recursive replies (e.g. limit depth/nesting for JSON optimization)
            "replies": [APISerializer.comment(reply, current_user) for reply in comment.replies.all()]
        }

    @staticmethod
    def notification(notification):
        """Notification serialization."""
        if not notification:
            return None
        return {
            "id": notification.id,
            "notification_type": notification.notification_type,
            "message": notification.message,
            "link_url": notification.link_url,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
            "sender": APISerializer.user_basic(notification.sender)
        }
