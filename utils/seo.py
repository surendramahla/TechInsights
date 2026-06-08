import re
import unicodedata
from flask import url_for

def slugify(text):
    """
    Convert a string into a clean, URL-friendly slug.
    Example: "Getting Started with Python!" -> "getting-started-with-python"
    """
    if not text:
        return ""
    # Normalize unicode characters to replace accents/non-latin characters
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase
    text = text.lower()
    # Remove non-alphanumeric characters (keep alphanumeric, spaces, and dashes)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Replace multiple spaces/dashes with a single dash
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def generate_json_ld(blog):
    """
    Generate JSON-LD structured data for a blog post (Schema.org BlogPosting).
    """
    if not blog:
        return {}
    
    cover_url = ""
    if blog.cover_image:
        if blog.cover_image.startswith('http'):
            cover_url = blog.cover_image
        else:
            cover_url = url_for('static', filename='uploads/' + blog.cover_image, _external=True)
    else:
        cover_url = url_for('static', filename='images/default_cover.jpg', _external=True)

    author_url = url_for('user_profile', username=blog.author.username, _external=True)
    
    excerpt_text = ""
    if hasattr(blog, 'excerpt'):
        excerpt_text = blog.excerpt(150)
    else:
        # Strip HTML tags
        excerpt_text = re.sub(r'<[^>]+>', '', blog.content or '')[:150]
    
    # Format date
    pub_date = blog.date_posted.isoformat() if hasattr(blog.date_posted, 'isoformat') else str(blog.date_posted)
    
    # Standard slug route URL
    blog_slug = blog.slug or slugify(blog.title)
    main_url = url_for('blog_detail', blog_id=blog.id, slug=blog_slug, _external=True)
    
    return {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": blog.title,
        "image": cover_url,
        "datePublished": pub_date,
        "author": {
            "@type": "Person",
            "name": blog.author.username,
            "url": author_url
        },
        "publisher": {
            "@type": "Organization",
            "name": "TechInsights",
            "logo": {
                "@type": "ImageObject",
                "url": url_for('static', filename='logo.png', _external=True) # Fallback to server logo
            }
        },
        "description": excerpt_text,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": main_url
        }
    }
