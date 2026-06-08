import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup
import re
import time

# Cache to avoid recalculating TF-IDF matrix for every single page load
_rec_cache = {
    'last_updated': 0,
    'sim_matrix': None,
    'df': None,
    'blog_count': 0
}

def clean_text(html_content):
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r'\s+', ' ', text).strip().lower()

def update_recommendation_cache(all_blogs):
    if not all_blogs:
        return
        
    data = []
    for blog in all_blogs:
        tags = " ".join([t.name for t in blog.tags])
        content = clean_text(blog.content)
        title = blog.title.lower()
        # Give more weight to tags and title by repeating them
        combined_text = f"{title} {title} {tags} {tags} {tags} {content}"
        data.append({'id': blog.id, 'text': combined_text})
        
    df = pd.DataFrame(data)
    
    # TF-IDF Vectorizer
    tfidf = TfidfVectorizer(stop_words='english', max_features=5000)
    try:
        tfidf_matrix = tfidf.fit_transform(df['text'])
        cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
        
        _rec_cache['sim_matrix'] = cosine_sim
        _rec_cache['df'] = df
        _rec_cache['last_updated'] = time.time()
        _rec_cache['blog_count'] = len(all_blogs)
    except ValueError:
        # Fails if vocabulary is empty
        pass

def get_recommendations(target_blog_id, all_blogs, top_n=4):
    """
    Get recommended blogs based on TF-IDF Cosine Similarity of content, titles, and tags.
    """
    if not all_blogs or len(all_blogs) < 2:
        return []
        
    # Rebuild cache if we have new blogs
    if _rec_cache['blog_count'] != len(all_blogs) or _rec_cache['sim_matrix'] is None:
        update_recommendation_cache(all_blogs)
        
    df = _rec_cache['df']
    cosine_sim = _rec_cache['sim_matrix']
    
    if df is None or cosine_sim is None:
        return []
        
    try:
        # Find index of target blog
        idx = df.index[df['id'] == target_blog_id].tolist()[0]
    except IndexError:
        return []
        
    # Get similarity scores
    sim_scores = list(enumerate(cosine_sim[idx]))
    
    # Sort by similarity
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    
    recommended_ids = []
    for i, score in sim_scores:
        if i != idx: # Skip itself
            recommended_ids.append(df.iloc[i]['id'])
        if len(recommended_ids) == top_n:
            break
            
    # Map IDs back to Blog objects in correct order
    id_to_blog = {b.id: b for b in all_blogs}
    rec_blogs = [id_to_blog[rid] for rid in recommended_ids if rid in id_to_blog]
    
    return rec_blogs
