"""
Trend Discovery Module
Discovers trending topics using pytrends (Google Trends) with Gemini AI fallback.
"""

import json
import random
from datetime import datetime
from pathlib import Path

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class TrendDiscovery:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.gemini_client = None
        self.gemini_model = self.config['gemini']['model']
        
        if GEMINI_AVAILABLE and self.config['gemini']['api_key'] != "YOUR_GEMINI_API_KEY_HERE":
            self.gemini_client = genai.Client(api_key=self.config['gemini']['api_key'])
        
        if PYTRENDS_AVAILABLE:
            self.pytrends = TrendReq(hl='en-US', tz=360)
        else:
            self.pytrends = None

    def get_trending_from_pytrends(self, country: str = 'united_states') -> list[dict]:
        """Fetch trending searches from Google Trends via pytrends."""
        if not self.pytrends:
            return []
        
        try:
            # Get daily trending searches
            trending_df = self.pytrends.trending_searches(pn=country)
            topics = trending_df[0].tolist()[:20]  # Get top 20
            
            return [{"topic": topic, "source": "pytrends"} for topic in topics]
        except Exception as e:
            print(f"pytrends error: {e}")
            return []

    def get_related_topics(self, keyword: str) -> list[dict]:
        """Get related topics for a keyword to expand quiz ideas."""
        if not self.pytrends:
            return []
        
        try:
            self.pytrends.build_payload([keyword], timeframe='today 3-m')
            related = self.pytrends.related_queries()
            
            if keyword in related and related[keyword]['rising'] is not None:
                rising = related[keyword]['rising']['query'].tolist()[:5]
                return [{"topic": t, "source": "pytrends_related"} for t in rising]
            return []
        except Exception as e:
            print(f"Related topics error: {e}")
            return []

    def get_trending_from_gemini(self, category: str, quiz_type: str) -> list[dict]:
        """Use Gemini to suggest trending/popular quiz topics."""
        if not self.gemini_client:
            return []
        
        prompt = f"""Suggest 5 currently popular or evergreen topics for a {quiz_type} quiz in the {category} category.

For personality quizzes, suggest "Which X are you?" style topics.
For trivia quizzes, suggest knowledge-testing topics.

Return ONLY a JSON array of objects with "topic" and "description" keys.
Example: [{{"topic": "Christmas Movies", "description": "Which Christmas movie character matches your personality?"}}]

Focus on topics that are:
- Currently trending or seasonally relevant (it's {datetime.now().strftime('%B %Y')})
- Broadly appealing
- Fun and engaging

Return valid JSON only, no markdown formatting."""

        try:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )
            text = response.text.strip()
            # Clean up potential markdown formatting
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                text = text.rsplit('```', 1)[0]
            
            topics = json.loads(text)
            return [{"topic": t['topic'], "description": t.get('description', ''), "source": "gemini"} for t in topics]
        except Exception as e:
            print(f"Gemini error: {e}")
            return []

    def discover_topics(self, quiz_type: str, category: str, use_pytrends: bool = True) -> list[dict]:
        """
        Main method to discover quiz topics.
        Tries pytrends first, falls back to Gemini.
        """
        topics = []
        
        # Try pytrends if enabled
        if use_pytrends and PYTRENDS_AVAILABLE:
            print("Fetching trends from Google Trends...")
            trending = self.get_trending_from_pytrends()
            topics.extend(trending[:5])
        
        # Supplement or fallback with Gemini
        if len(topics) < 5:
            print("Using Gemini for topic suggestions...")
            gemini_topics = self.get_trending_from_gemini(category, quiz_type)
            topics.extend(gemini_topics)
        
        # Deduplicate by topic name
        seen = set()
        unique_topics = []
        for t in topics:
            if t['topic'].lower() not in seen:
                seen.add(t['topic'].lower())
                unique_topics.append(t)
        
        return unique_topics[:10]  # Return top 10


def main():
    """Test the trend discovery module."""
    discovery = TrendDiscovery()
    
    print("=" * 50)
    print("Testing Trend Discovery")
    print("=" * 50)
    
    # Test personality quiz topics
    print("\n[Personality Quiz - Pop Culture]")
    topics = discovery.discover_topics("personality", "pop_culture")
    for t in topics:
        print(f"  - {t['topic']} (via {t['source']})")
    
    # Test trivia quiz topics
    print("\n[Trivia Quiz - History]")
    topics = discovery.discover_topics("trivia", "history")
    for t in topics:
        print(f"  - {t['topic']} (via {t['source']})")


if __name__ == "__main__":
    main()
