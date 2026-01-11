"""
Hybrid Image Generator Module
Uses Unsplash for cover/outcome images (professional, reliable)
Uses Pollinations AI for question images (creative, unique)
"""

import json
import time
import urllib.parse
import urllib.request
import urllib.error
import random
import re
import os
from pathlib import Path


class ImageGenerator:
    """
    Hybrid image generator that combines:
    - Unsplash API for cover and outcome images (professional stock photos)
    - Pollinations AI for question images (creative AI-generated illustrations)
    """
    
    # Words that might trigger human generation in AI - we'll filter these out
    HUMAN_TRIGGER_WORDS = [
        'person', 'people', 'human', 'man', 'woman', 'boy', 'girl', 'child',
        'face', 'portrait', 'character', 'figure', 'body', 'hand', 'hands',
        'eye', 'eyes', 'smile', 'smiling', 'looking', 'standing', 'sitting',
        'walking', 'running', 'holding', 'wearing', 'dressed', 'crowd',
        'group of people', 'family', 'friends', 'team', 'audience',
        'he', 'she', 'they', 'him', 'her', 'his', 'their',
        'someone', 'somebody', 'anyone', 'everybody', 'everyone',
        'celebrity', 'actor', 'actress', 'player', 'athlete',
        'wizard', 'witch', 'hero', 'heroine', 'villain', 'warrior',
        'king', 'queen', 'prince', 'princess', 'knight',
        'student', 'teacher', 'doctor', 'nurse', 'worker', 'boss',
        'baby', 'toddler', 'teenager', 'adult', 'elder', 'elderly',
        'guy', 'gal', 'dude', 'lady', 'gentleman', 'kid', 'kids',
        'selfie', 'headshot', 'mugshot', 'avatar',
        'expression', 'expressions', 'facial', 'emotion', 'emotions',
    ]
    
    # Strong negative prompt to prevent human generation AND text in AI images
    NO_HUMANS_NEGATIVE = (
        "absolutely no humans, no people, no faces, no portraits, no characters, "
        "no figures, no bodies, no hands, no eyes, no facial features, "
        "no men, no women, no children, no silhouettes of people, "
        "no text, no words, no letters, no numbers, no writing, no captions, "
        "no labels, no signs, no typography, no fonts, no watermarks, "
        "objects and symbols only, illustration style"
    )
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # ============== UNSPLASH CONFIG ==============
        unsplash_config = self.config.get('unsplash', {})
        self.unsplash_access_key = unsplash_config.get('access_key', '')
        self.unsplash_base_url = "https://api.unsplash.com"
        
        # ============== POLLINATIONS CONFIG ==============
        pollinations_config = self.config.get('pollinations', {})
        self.pollinations_base_url = pollinations_config.get('base_url', 'https://image.pollinations.ai/prompt')
        self.pollinations_api_key = pollinations_config.get('api_key', '')
        self.pollinations_model = pollinations_config.get('model', 'flux')
        
        # Style suffix for AI images
        self.style_suffix = pollinations_config.get(
            'style_suffix', 
            'illustration style, no humans, no people, no faces, no text, no words, vibrant colors, detailed'
        )
        
        # AI image features
        self.enhance_prompt = pollinations_config.get('enhance', False)
        self.private = pollinations_config.get('private', False)
        self.safe_mode = pollinations_config.get('safe', True)
        self.nologo = pollinations_config.get('nologo', True)
        
        # ============== SHARED CONFIG ==============
        # Image dimensions
        self.cover_width = pollinations_config.get('cover_width', 1200)
        self.cover_height = pollinations_config.get('cover_height', 630)
        self.question_width = pollinations_config.get('question_width', 800)
        self.question_height = pollinations_config.get('question_height', 450)
        self.outcome_width = pollinations_config.get('outcome_width', 600)
        self.outcome_height = pollinations_config.get('outcome_height', 600)
        
        # Retry settings
        self.max_retries = pollinations_config.get('max_retries', 3)
        self.base_delay = pollinations_config.get('retry_delay_seconds', 5)
        self.timeout = pollinations_config.get('timeout_seconds', 120)
        self.request_delay = pollinations_config.get('request_delay_seconds', 5)
        
        # Log configuration status
        self._log_config_status()
    
    def _log_config_status(self):
        """Log the configuration status for debugging."""
        print("\n[Image Generator Configuration]")
        if self.unsplash_access_key and self.unsplash_access_key != "YOUR_UNSPLASH_ACCESS_KEY_HERE":
            print("  ✓ Unsplash: Configured (for covers & outcomes)")
        else:
            print("  ⚠ Unsplash: Not configured - will fall back to AI for all images")
            print("    Get a free API key at: https://unsplash.com/developers")
        
        if self.pollinations_api_key and self.pollinations_api_key != "YOUR_POLLINATIONS_API_KEY_HERE":
            print("  ✓ Pollinations: Configured with API key (for questions)")
        else:
            print("  ⚠ Pollinations: Using anonymous tier (for questions)")
        print()

    # ================================================================
    #                    UNSPLASH METHODS (Stock Photos)
    # ================================================================
    
    def _search_unsplash(self, query: str, width: int = 1200, height: int = 630) -> str:
        """
        Search Unsplash for a photo matching the query.
        Returns the download URL or None if not found.
        """
        if not self.unsplash_access_key or self.unsplash_access_key == "YOUR_UNSPLASH_ACCESS_KEY_HERE":
            return None
        
        # Clean up query for better search results
        search_query = self._simplify_search_query(query)
        
        try:
            # Build search URL
            params = urllib.parse.urlencode({
                'query': search_query,
                'per_page': 10,
                'orientation': 'landscape' if width > height else 'squarish'
            })
            url = f"{self.unsplash_base_url}/search/photos?{params}"
            
            # Make request
            request = urllib.request.Request(url)
            request.add_header('Authorization', f'Client-ID {self.unsplash_access_key}')
            request.add_header('Accept-Version', 'v1')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())
                
                if data['results']:
                    # Pick a random photo from top results for variety
                    photo = random.choice(data['results'][:5])
                    
                    # Get the sized URL
                    raw_url = photo['urls']['raw']
                    sized_url = f"{raw_url}&w={width}&h={height}&fit=crop&crop=entropy"
                    
                    return sized_url
                    
        except Exception as e:
            print(f"  ⚠ Unsplash search failed: {e}")
        
        return None
    
    def _simplify_search_query(self, prompt: str) -> str:
        """
        Simplify a detailed image prompt into good Unsplash search keywords.
        """
        # Remove common filler words and instructions
        remove_phrases = [
            'a vibrant', 'eye-catching', 'cover illustration', 'illustration',
            'for a quiz', 'about', 'using only', 'symbols', 'icons', 'objects',
            'patterns', 'fun and inviting', 'style', 'absolutely no', 'no humans',
            'no people', 'no faces', 'no characters', 'no text', 'no words',
            'no letters', 'no writing', 'detailed', 'vibrant colors',
            'dynamic', 'exciting', 'trivia', 'personality', 'quiz',
            'knowledge and discovery theme', 'with books', 'question marks',
            'light bulbs', 'and symbols', 'objects and symbols only',
            'professional', 'high quality', 'beautiful', 'stunning'
        ]
        
        simplified = prompt.lower()
        for phrase in remove_phrases:
            simplified = simplified.replace(phrase.lower(), '')
        
        # Clean up extra spaces and commas
        simplified = re.sub(r'[,]+', ' ', simplified)
        simplified = ' '.join(simplified.split())
        
        # Take first few meaningful words (max 4-5 words work best for Unsplash)
        words = simplified.split()[:5]
        
        return ' '.join(words).strip()
    
    def _download_unsplash_image(self, url: str, filepath: Path) -> bool:
        """Download an image from Unsplash URL."""
        try:
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'QuizPlatform/1.0')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                with open(filepath, 'wb') as f:
                    f.write(response.read())
            
            return filepath.exists() and filepath.stat().st_size > 1000
            
        except Exception as e:
            print(f"  ⚠ Download failed: {e}")
            return False

    def generate_stock_image(self, query: str, filename: str, output_dir: str,
                             width: int = 1200, height: int = 630) -> str:
        """
        Generate/download a stock image from Unsplash.
        
        Args:
            query: Search query or description
            filename: Name for the saved file (without extension)
            output_dir: Directory to save images
            width: Desired image width
            height: Desired image height
        
        Returns:
            Path to saved image, or None if failed
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        filepath = output_path / f"{filename}.jpg"
        
        print(f"  Searching Unsplash: {self._simplify_search_query(query)[:50]}...")
        
        # Search for image
        image_url = self._search_unsplash(query, width, height)
        
        if image_url:
            if self._download_unsplash_image(image_url, filepath):
                print(f"  ✓ Saved (Unsplash): {filepath}")
                time.sleep(1)  # Be nice to API
                return str(filepath)
        
        print(f"  ⚠ Unsplash failed, falling back to AI...")
        return None

    # ================================================================
    #                 POLLINATIONS METHODS (AI Images)
    # ================================================================
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """
        Remove or replace words that might trigger human generation.
        Only used for AI-generated images.
        """
        sanitized = prompt.lower()
        
        # Replacements for common human-related terms
        replacements = {
            'person': 'silhouette shape',
            'people': 'abstract shapes',
            'character': 'symbol',
            'characters': 'symbols',
            'figure': 'shape',
            'figures': 'shapes',
            'hero': 'heroic emblem',
            'heroine': 'heroic emblem',
            'villain': 'dark emblem',
            'wizard': 'magical staff and pointed hat',
            'witch': 'cauldron and broomstick',
            'warrior': 'sword and shield emblem',
            'king': 'golden crown on cushion',
            'queen': 'silver tiara on cushion',
            'prince': 'royal crest emblem',
            'princess': 'royal crest emblem',
            'knight': 'suit of armor display',
            'man': 'masculine symbol',
            'woman': 'feminine symbol',
            'boy': 'small emblem',
            'girl': 'small emblem',
            'child': 'tiny emblem',
            'children': 'tiny emblems',
            'baby': 'baby rattle and blanket',
            'toddler': 'small toys',
            'teenager': 'youth symbol',
            'adult': 'mature emblem',
            'elder': 'wisdom symbol',
            'elderly': 'wisdom symbols',
            'family': 'connected heart symbols',
            'friends': 'linked circle emblems',
            'team': 'united star emblems',
            'crowd': 'pattern of dots',
            'audience': 'rows of empty seats',
            'celebrity': 'gold star',
            'actor': 'theater masks',
            'actress': 'theater masks',
            'player': 'game controller',
            'athlete': 'sports equipment',
            'student': 'books and pencils',
            'teacher': 'chalkboard and apple',
            'doctor': 'stethoscope',
            'nurse': 'medical cross',
            'worker': 'tools',
            'boss': 'desk and nameplate',
            'guy': 'abstract shape',
            'gal': 'abstract shape',
            'dude': 'abstract shape',
            'lady': 'elegant symbol',
            'gentleman': 'top hat and cane',
            'kid': 'small toy',
            'kids': 'small toys',
            'face': 'decorative mask',
            'faces': 'decorative masks',
            'portrait': 'framed artwork',
            'selfie': 'camera icon',
            'headshot': 'photo frame',
            'avatar': 'icon symbol',
            'expression': 'emoji icon',
            'expressions': 'emoji icons',
            'facial': 'mask design',
            'emotion': 'heart symbol',
            'emotions': 'heart symbols',
            'someone': 'something',
            'somebody': 'something',
            'everyone': 'everything',
            'everybody': 'everything',
            'anyone': 'anything',
            # Text-related replacements
            'text': 'pattern',
            'words': 'shapes',
            'word': 'shape',
            'letters': 'symbols',
            'letter': 'symbol',
            'writing': 'decoration',
            'sign': 'banner shape',
            'signs': 'banner shapes',
            'label': 'tag shape',
            'labels': 'tag shapes',
            'title': 'decorative header',
            'caption': 'decorative element',
            'quote': 'decorative flourish',
            'message': 'visual element',
        }
        
        for old, new in replacements.items():
            sanitized = re.sub(r'\b' + old + r'\b', new, sanitized, flags=re.IGNORECASE)
        
        # Remove pronouns that suggest humans
        pronouns = ['he ', 'she ', 'him ', 'her ', 'his ', 'their ', 'they ']
        for pronoun in pronouns:
            sanitized = sanitized.replace(pronoun, '')
        
        # Remove action verbs that imply human activity
        human_actions = [
            'standing', 'sitting', 'walking', 'running', 'holding',
            'wearing', 'dressed', 'looking', 'smiling', 'laughing',
            'talking', 'speaking', 'pointing', 'waving'
        ]
        for action in human_actions:
            sanitized = re.sub(r'\b' + action + r'\b', '', sanitized, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        sanitized = ' '.join(sanitized.split())
        
        return sanitized

    def _build_safe_prompt(self, prompt: str) -> str:
        """Build a prompt safe from generating humans/text."""
        sanitized = self._sanitize_prompt(prompt)
        safe_prompt = f"{sanitized}, {self.style_suffix}, {self.NO_HUMANS_NEGATIVE}"
        return safe_prompt

    def generate_ai_image(self, prompt: str, filename: str, output_dir: str,
                          width: int = 800, height: int = 450) -> str:
        """
        Generate an AI image using Pollinations.ai.
        Includes guardrails against humans and text.
        
        Args:
            prompt: Text description for the image
            filename: Name for the saved file (without extension)
            output_dir: Directory to save images
            width: Image width
            height: Image height
        
        Returns:
            Path to saved image, or None if failed
        """
        # Build safe prompt with guardrails
        safe_prompt = self._build_safe_prompt(prompt)
        encoded_prompt = urllib.parse.quote(safe_prompt)
        
        seed = random.randint(1, 999999)
        
        # Build URL with parameters
        params = [
            f"width={width}",
            f"height={height}",
            f"seed={seed}",
            f"model={self.pollinations_model}",
            f"nologo={str(self.nologo).lower()}",
            f"safe={str(self.safe_mode).lower()}",
        ]
        
        if self.enhance_prompt:
            params.append("enhance=true")
        if self.private:
            params.append("private=true")
        if self.pollinations_api_key and self.pollinations_api_key != "YOUR_POLLINATIONS_API_KEY_HERE":
            params.append(f"key={self.pollinations_api_key}")
        
        url = f"{self.pollinations_base_url}/{encoded_prompt}?{'&'.join(params)}"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        filepath = output_path / f"{filename}.png"
        
        # Retry loop
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"  Generating AI image: {filename} (attempt {attempt}/{self.max_retries})...")
                
                request = urllib.request.Request(url)
                request.add_header('User-Agent', 'QuizPlatform/1.0')
                
                if self.pollinations_api_key and self.pollinations_api_key != "YOUR_POLLINATIONS_API_KEY_HERE":
                    request.add_header('Authorization', f'Bearer {self.pollinations_api_key}')
                
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' not in content_type:
                        raise ValueError(f"Expected image, got {content_type}")
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.read())
                
                if filepath.exists() and filepath.stat().st_size > 1000:
                    print(f"  ✓ Saved (AI): {filepath}")
                    time.sleep(self.request_delay)
                    return str(filepath)
                else:
                    raise ValueError("Generated file is too small or empty")
            
            except urllib.error.HTTPError as e:
                print(f"  ⚠ HTTP Error {e.code}: {e.reason}")
                if e.code in [502, 503, 504, 429]:
                    if attempt < self.max_retries:
                        delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 2)
                        print(f"    Waiting {delay:.1f}s before retry...")
                        time.sleep(delay)
                        continue
                elif e.code == 401:
                    print(f"  ✗ Authentication failed. Check your API key.")
                    break
                else:
                    break
            
            except Exception as e:
                print(f"  ⚠ Error: {e}")
                if attempt < self.max_retries:
                    delay = self.base_delay * attempt
                    print(f"    Waiting {delay}s before retry...")
                    time.sleep(delay)
                    continue
        
        print(f"  ✗ Failed to generate {filename} after {self.max_retries} attempts")
        return None

    # ================================================================
    #                    HYBRID QUIZ IMAGE GENERATION
    # ================================================================
    
    def generate_quiz_images(self, quiz: dict, output_dir: str = "data/images") -> dict:
        """
        Generate all images for a quiz using hybrid approach:
        - Cover: Unsplash (stock photo)
        - Questions: Pollinations AI (illustrations)
        - Outcomes: Unsplash (stock photo)
        
        Falls back to AI if Unsplash fails or is not configured.
        """
        quiz_id = quiz['id']
        quiz_dir = Path(output_dir) / quiz_id
        quiz_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*50}")
        print(f"Generating images for: {quiz['title']}")
        print(f"{'='*50}")
        
        success_count = 0
        fail_count = 0
        
        # ============== COVER IMAGE (Unsplash) ==============
        if 'coverImagePrompt' in quiz:
            print(f"\n[Cover Image - Stock Photo]")
            cover_path = self.generate_stock_image(
                quiz.get('stockSearchQuery', quiz['coverImagePrompt']),
                "cover",
                str(quiz_dir),
                width=self.cover_width,
                height=self.cover_height
            )
            
            # Fallback to AI if Unsplash fails
            if not cover_path:
                print("  Falling back to AI generation...")
                cover_path = self.generate_ai_image(
                    quiz['coverImagePrompt'],
                    "cover",
                    str(quiz_dir),
                    width=self.cover_width,
                    height=self.cover_height
                )
            
            if cover_path:
                ext = Path(cover_path).suffix
                quiz['coverImage'] = f"/images/{quiz_id}/cover{ext}"
                success_count += 1
            else:
                fail_count += 1
        
        # ============== QUESTION IMAGES (AI) ==============
        print(f"\n[Question Images - AI Generated]")
        for i, question in enumerate(quiz['questions']):
            if 'imagePrompt' in question:
                q_path = self.generate_ai_image(
                    question['imagePrompt'],
                    f"question-{i+1}",
                    str(quiz_dir),
                    width=self.question_width,
                    height=self.question_height
                )
                if q_path:
                    question['image'] = f"/images/{quiz_id}/question-{i+1}.png"
                    success_count += 1
                else:
                    fail_count += 1
        
        # ============== OUTCOME IMAGES (Unsplash) ==============
        if quiz['type'] == 'personality' and 'outcomes' in quiz:
            print(f"\n[Outcome Images - Stock Photos]")
            for outcome_id, outcome in quiz['outcomes'].items():
                if 'imagePrompt' in outcome:
                    # Use outcome title as search query for better results
                    search_query = outcome.get('stockSearchQuery', outcome.get('title', outcome_id))
                    
                    o_path = self.generate_stock_image(
                        search_query,
                        f"outcome-{outcome_id}",
                        str(quiz_dir),
                        width=self.outcome_width,
                        height=self.outcome_height
                    )
                    
                    # Fallback to AI if Unsplash fails
                    if not o_path:
                        print("  Falling back to AI generation...")
                        o_path = self.generate_ai_image(
                            outcome['imagePrompt'],
                            f"outcome-{outcome_id}",
                            str(quiz_dir),
                            width=self.outcome_width,
                            height=self.outcome_height
                        )
                    
                    if o_path:
                        ext = Path(o_path).suffix
                        outcome['image'] = f"/images/{quiz_id}/outcome-{outcome_id}{ext}"
                        success_count += 1
                    else:
                        fail_count += 1
        
        # ============== SUMMARY ==============
        print(f"\n{'='*50}")
        print(f"✓ Image generation complete for {quiz_id}")
        print(f"  Success: {success_count} | Failed: {fail_count}")
        if fail_count > 0:
            print(f"  💡 Tip: Run retry_failed_images() to attempt recovery")
        print(f"{'='*50}\n")
        
        return quiz

    def retry_failed_images(self, quiz: dict, output_dir: str = "data/images") -> dict:
        """Retry generating only the missing images for a quiz."""
        quiz_id = quiz['id']
        quiz_dir = Path(output_dir) / quiz_id
        quiz_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nRetrying failed images for: {quiz['title']}")
        print("-" * 40)
        
        retried = 0
        
        # Check cover image
        if 'coverImagePrompt' in quiz and not quiz.get('coverImage'):
            cover_path = self.generate_stock_image(
                quiz.get('stockSearchQuery', quiz['coverImagePrompt']),
                "cover", str(quiz_dir),
                width=self.cover_width, height=self.cover_height
            )
            if not cover_path:
                cover_path = self.generate_ai_image(
                    quiz['coverImagePrompt'], "cover", str(quiz_dir),
                    width=self.cover_width, height=self.cover_height
                )
            if cover_path:
                ext = Path(cover_path).suffix
                quiz['coverImage'] = f"/images/{quiz_id}/cover{ext}"
                retried += 1
        
        # Check question images
        for i, question in enumerate(quiz['questions']):
            if 'imagePrompt' in question and not question.get('image'):
                q_path = self.generate_ai_image(
                    question['imagePrompt'], f"question-{i+1}", str(quiz_dir),
                    width=self.question_width, height=self.question_height
                )
                if q_path:
                    question['image'] = f"/images/{quiz_id}/question-{i+1}.png"
                    retried += 1
        
        # Check outcome images
        if quiz['type'] == 'personality' and 'outcomes' in quiz:
            for outcome_id, outcome in quiz['outcomes'].items():
                if 'imagePrompt' in outcome and not outcome.get('image'):
                    search_query = outcome.get('stockSearchQuery', outcome.get('title', outcome_id))
                    o_path = self.generate_stock_image(
                        search_query, f"outcome-{outcome_id}", str(quiz_dir),
                        width=self.outcome_width, height=self.outcome_height
                    )
                    if not o_path:
                        o_path = self.generate_ai_image(
                            outcome['imagePrompt'], f"outcome-{outcome_id}", str(quiz_dir),
                            width=self.outcome_width, height=self.outcome_height
                        )
                    if o_path:
                        ext = Path(o_path).suffix
                        outcome['image'] = f"/images/{quiz_id}/outcome-{outcome_id}{ext}"
                        retried += 1
        
        print(f"\n✓ Retry complete: {retried} images recovered")
        return quiz

    def list_available_models(self) -> list:
        """Fetch list of available Pollinations AI models."""
        try:
            url = "https://image.pollinations.ai/models"
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'QuizPlatform/1.0')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Failed to fetch models: {e}")
            return []


def main():
    """Test the hybrid image generator."""
    generator = ImageGenerator()
    
    print("\n" + "="*50)
    print("Testing Hybrid Image Generator")
    print("="*50)
    
    # Test Unsplash
    print("\n[Test 1: Unsplash Stock Photo]")
    result = generator.generate_stock_image(
        "magical fantasy castle",
        "test-stock",
        "data/images/test",
        width=1200,
        height=630
    )
    print(f"Result: {result or 'Failed'}")
    
    # Test Pollinations AI
    print("\n[Test 2: Pollinations AI]")
    result = generator.generate_ai_image(
        "A magical winter scene with snowflakes and warm golden lights",
        "test-ai",
        "data/images/test",
        width=800,
        height=450
    )
    print(f"Result: {result or 'Failed'}")


if __name__ == "__main__":
    main()
