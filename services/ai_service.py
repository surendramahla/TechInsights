import os
import requests
from bs4 import BeautifulSoup
import re

# Prefer OpenAI if available, fallback to HuggingFace
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
HF_API_KEY = os.environ.get('HF_API_KEY')

def clean_html(html_content):
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r'\s+', ' ', text).strip()

def generate_summary(html_content):
    """Generate a concise summary of the blog content using AI."""
    text = clean_html(html_content)
    if not text or len(text) < 100:
        return "Content is too short to summarize."

    # 1. Try OpenAI
    if OPENAI_API_KEY:
        try:
            import openai
            openai.api_key = OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": f"Provide a concise, professional 2-3 sentence summary of the following article:\n\n{text[:3000]}..."}],
                max_tokens=150
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            print(f"OpenAI error: {e}")

    # 2. Try HuggingFace Free Inference API
    try:
        API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
        # Wait for model if loading, using free tier
        payload = {"inputs": text[:2000], "parameters": {"max_length": 100, "min_length": 30}}
        response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()[0]['summary_text']
    except Exception as e:
        print(f"HF API error: {e}")

    # 3. Fallback to Local Transformers
    try:
        from transformers import pipeline
        # Use a small model to prevent heavy memory usage locally
        summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        summary = summarizer(text[:1500], max_length=100, min_length=30, do_sample=False)
        return summary[0]['summary_text']
    except ImportError:
        return "AI Summarization unavailable. Please set an API key or install transformers."
    except Exception as e:
        print(f"Local Transformers Error: {e}")
        return "Error generating summary."


def generate_tags(html_content, num_tags=5):
    """Generate intelligent tags using NLP (YAKE)."""
    text = clean_html(html_content)
    if not text:
        return []
    
    try:
        import yake
        # YAKE is great for fast, unsupervised keyword extraction
        kw_extractor = yake.KeywordExtractor(lan="en", n=1, dedupLim=0.9, top=num_tags*2, features=None)
        keywords = kw_extractor.extract_keywords(text)
        
        # Clean and filter tags
        tags = []
        for kw, score in keywords:
            tag = re.sub(r'[^a-zA-Z0-9]', '', kw).lower()
            if len(tag) > 2 and tag not in tags:
                tags.append(tag)
            if len(tags) >= num_tags:
                break
        return tags
    except ImportError:
        print("YAKE not installed.")
        return []
    except Exception as e:
        print(f"Tag generation error: {e}")
        return []


def analyze_sentiment(html_content):
    """Analyze the tone/sentiment of the article."""
    text = clean_html(html_content)
    if not text:
        return "Neutral"
        
    try:
        from transformers import pipeline
        sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
        result = sentiment_analyzer(text[:512])[0]
        # Map output
        label = result['label']
        if label == 'POSITIVE':
            return "Positive"
        elif label == 'NEGATIVE':
            return "Negative"
        return "Neutral"
    except ImportError:
        return "Neutral"
    except Exception as e:
        print(f"Sentiment error: {e}")
        return "Neutral"


def generate_title(html_content):
    """Suggest a title based on content using HuggingFace."""
    text = clean_html(html_content)
    if not text or len(text) < 50:
        return ""
        
    try:
        API_URL = "https://api-inference.huggingface.co/models/czearing/article-title-generator"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
        payload = {"inputs": text[:1000]}
        response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()[0]['generated_text']
    except Exception:
        pass
    return ""
