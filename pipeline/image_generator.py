"""
Image Generator Module
Generates images for quizzes using Pollinations.ai API.
Updated for the latest Pollinations API (2026) with authentication support.
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
    # Words that might trigger human generation - we'll filter these out
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
    
    # Strong negative prompt to prevent human generation AND text - VERY explicit
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
        
        pollinations_config = self.config['pollinations']
        
        # API configuration - supports both legacy and new authenticated API
        self.base_url = pollinations_config.get('base_url', 'https://image.pollinations.ai/prompt')
        self.api_key = pollinations_config.get('api_key', '')
        
        # Model selection (flux is the default, turbo is faster)
        self.model = pollinations_config.get('model', 'flux')
        
        # Image dimensions for different types
        self.cover_width = pollinations_config.get('cover_width', 1200)
        self.cover_height = pollinations_config.get('cover_height', 630)
        self.question_width = pollinations_config.get('question_width', 800)
        self.question_height = pollinations_config.get('question_height', 450)
        self.outcome_width = pollinations_config.get('outcome_width', 600)
        self.outcome_height = pollinations_config.get('outcome_height', 600)
        
        # Style suffix to avoid humans and ensure consistent style
        self.style_suffix = pollinations_config.get(
            'style_suffix', 
            'illustration style, no humans, no people, no faces, vibrant colors, detailed'
        )
        
        # API features
        self.enhance_prompt = pollinations_config.get('enhance', False)
        self.private = pollinations_config.get('private', False)
        self.safe_mode = pollinations_config.get('safe', True)
        self.nologo = pollinations_config.get('nologo', True)
        
        # Retry settings
        self.max_retries = pollinations_config.get('max_retries', 3)
        self.base_delay = pollinations_config.get('retry_delay_seconds', 5)
        self.timeout = pollinations_config.get('timeout_seconds', 120)
        
        # Rate limiting based on tier
        # Anonymous: 15s, Seed (free registered): 5s, Flower (paid): 3s, Nectar: no limit
        self.request_delay = pollinations_config.get('request_delay_seconds', 5)

    def _sanitize_prompt(self, prompt: str) -> str:
        """
        Remove or replace words that might trigger human generation.
        Transforms human-centric prompts into object/symbol-based ones.
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
            # Use word boundaries to avoid partial replacements
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
        """
        Build a prompt that's safe from generating humans.
        Sanitizes input and adds strong negative guidance.
        """
        # First sanitize the prompt
        sanitized = self._sanitize_prompt(prompt)
        
        # Build the final prompt with style suffix and explicit no-humans instruction
        safe_prompt = f"{sanitized}, {self.style_suffix}, {self.NO_HUMANS_NEGATIVE}"
        
        return safe_prompt

    def generate_image(self, prompt: str, filename: str, output_dir: str = "data/images",
                       width: int = 800, height: int = 600) -> str:
        """
        Generate an image using Pollinations.ai and save it locally.
        Includes retry logic for handling temporary failures.
        Supports both authenticated and anonymous API access.
        
        Args:
            prompt: Text description for the image
            filename: Name for the saved file (without extension)
            output_dir: Directory to save images
            width: Image width
            height: Image height
        
        Returns:
            Path to the saved image, or None if all retries failed
        """
        # Build safe prompt with no-humans guardrails
        safe_prompt = self._build_safe_prompt(prompt)
        
        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(safe_prompt)
        
        # Add a random seed to avoid caching issues and get unique images
        seed = random.randint(1, 999999)
        
        # Build the Pollinations URL with API parameters
        params = [
            f"width={width}",
            f"height={height}",
            f"seed={seed}",
            f"model={self.model}",
            f"nologo={str(self.nologo).lower()}",
            f"safe={str(self.safe_mode).lower()}",
        ]
        
        # Add optional parameters
        if self.enhance_prompt:
            params.append("enhance=true")
        if self.private:
            params.append("private=true")
        
        # Add API key to URL if provided (alternative to Bearer token)
        if self.api_key:
            params.append(f"key={self.api_key}")
        
        url = f"{self.base_url}/{encoded_prompt}?{'&'.join(params)}"
        
        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        filepath = output_path / f"{filename}.png"
        
        # Retry loop
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"  Generating: {filename} (attempt {attempt}/{self.max_retries})...")
                
                # Create request with timeout
                request = urllib.request.Request(url)
                request.add_header('User-Agent', 'QuizPlatform/1.0')
                
                # Add Bearer token authentication if API key is provided
                if self.api_key:
                    request.add_header('Authorization', f'Bearer {self.api_key}')
                
                # Download with timeout
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    # Check if we got a valid image
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' not in content_type:
                        raise ValueError(f"Expected image, got {content_type}")
                    
                    # Save the image
                    with open(filepath, 'wb') as f:
                        f.write(response.read())
                
                # Verify file was created and has content
                if filepath.exists() and filepath.stat().st_size > 1000:
                    print(f"  ✓ Saved: {filepath}")
                    # Delay between requests based on tier
                    time.sleep(self.request_delay)
                    return str(filepath)
                else:
                    raise ValueError("Generated file is too small or empty")
            
            except urllib.error.HTTPError as e:
                print(f"  ⚠ HTTP Error {e.code}: {e.reason}")
                if e.code in [502, 503, 504, 429]:
                    # Bad Gateway / Service Unavailable / Gateway Timeout / Rate Limited
                    if attempt < self.max_retries:
                        delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 2)
                        print(f"    Waiting {delay:.1f}s before retry...")
                        time.sleep(delay)
                        continue
                elif e.code == 401:
                    print(f"  ✗ Authentication failed. Check your API key at enter.pollinations.ai")
                    break
                else:
                    # Other HTTP errors
                    break
            
            except urllib.error.URLError as e:
                print(f"  ⚠ URL Error: {e.reason}")
                if attempt < self.max_retries:
                    delay = self.base_delay * attempt
                    print(f"    Waiting {delay}s before retry...")
                    time.sleep(delay)
                    continue
            
            except TimeoutError:
                print(f"  ⚠ Request timed out after {self.timeout}s")
                if attempt < self.max_retries:
                    delay = self.base_delay * attempt
                    print(f"    Waiting {delay}s before retry...")
                    time.sleep(delay)
                    continue
            
            except Exception as e:
                print(f"  ✗ Error: {e}")
                if attempt < self.max_retries:
                    delay = self.base_delay * attempt
                    print(f"    Waiting {delay}s before retry...")
                    time.sleep(delay)
                    continue
        
        print(f"  ✗ Failed to generate {filename} after {self.max_retries} attempts")
        return None

    def generate_quiz_images(self, quiz: dict, output_dir: str = "data/images") -> dict:
        """
        Generate all images for a quiz (cover, questions, outcomes).
        
        Args:
            quiz: The quiz data dictionary
            output_dir: Base directory for images
        
        Returns:
            Updated quiz dict with image paths
        """
        quiz_id = quiz['id']
        quiz_dir = Path(output_dir) / quiz_id
        quiz_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nGenerating images for: {quiz['title']}")
        print("-" * 40)
        
        success_count = 0
        fail_count = 0
        
        # Generate cover image
        if 'coverImagePrompt' in quiz:
            cover_path = self.generate_image(
                quiz['coverImagePrompt'],
                "cover",
                str(quiz_dir),
                width=self.cover_width,
                height=self.cover_height
            )
            if cover_path:
                quiz['coverImage'] = f"/images/{quiz_id}/cover.png"
                success_count += 1
            else:
                fail_count += 1
        
        # Generate question images
        for i, question in enumerate(quiz['questions']):
            if 'imagePrompt' in question:
                q_path = self.generate_image(
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
        
        # Generate outcome images (personality quizzes only)
        if quiz['type'] == 'personality' and 'outcomes' in quiz:
            for outcome_id, outcome in quiz['outcomes'].items():
                if 'imagePrompt' in outcome:
                    o_path = self.generate_image(
                        outcome['imagePrompt'],
                        f"outcome-{outcome_id}",
                        str(quiz_dir),
                        width=self.outcome_width,
                        height=self.outcome_height
                    )
                    if o_path:
                        outcome['image'] = f"/images/{quiz_id}/outcome-{outcome_id}.png"
                        success_count += 1
                    else:
                        fail_count += 1
        
        print(f"\n✓ Image generation complete for {quiz_id}")
        print(f"  Success: {success_count} | Failed: {fail_count}")
        
        if fail_count > 0:
            print(f"  💡 Tip: Run again later to retry failed images, or try during off-peak hours")
            if not self.api_key:
                print(f"  💡 Tip: Get an API key at enter.pollinations.ai for better rate limits")
        
        return quiz

    def retry_failed_images(self, quiz: dict, output_dir: str = "data/images") -> dict:
        """
        Retry generating only the missing images for a quiz.
        
        Args:
            quiz: The quiz data dictionary
            output_dir: Base directory for images
        
        Returns:
            Updated quiz dict with image paths
        """
        quiz_id = quiz['id']
        quiz_dir = Path(output_dir) / quiz_id
        quiz_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nRetrying failed images for: {quiz['title']}")
        print("-" * 40)
        
        retried = 0
        
        # Check cover image
        if 'coverImagePrompt' in quiz and not quiz.get('coverImage'):
            cover_path = self.generate_image(
                quiz['coverImagePrompt'],
                "cover",
                str(quiz_dir),
                width=self.cover_width,
                height=self.cover_height
            )
            if cover_path:
                quiz['coverImage'] = f"/images/{quiz_id}/cover.png"
                retried += 1
        
        # Check question images
        for i, question in enumerate(quiz['questions']):
            if 'imagePrompt' in question and not question.get('image'):
                q_path = self.generate_image(
                    question['imagePrompt'],
                    f"question-{i+1}",
                    str(quiz_dir),
                    width=self.question_width,
                    height=self.question_height
                )
                if q_path:
                    question['image'] = f"/images/{quiz_id}/question-{i+1}.png"
                    retried += 1
        
        # Check outcome images
        if quiz['type'] == 'personality' and 'outcomes' in quiz:
            for outcome_id, outcome in quiz['outcomes'].items():
                if 'imagePrompt' in outcome and not outcome.get('image'):
                    o_path = self.generate_image(
                        outcome['imagePrompt'],
                        f"outcome-{outcome_id}",
                        str(quiz_dir),
                        width=self.outcome_width,
                        height=self.outcome_height
                    )
                    if o_path:
                        outcome['image'] = f"/images/{quiz_id}/outcome-{outcome_id}.png"
                        retried += 1
        
        print(f"\n✓ Retry complete: {retried} images recovered")
        return quiz

    def generate_single_image(self, prompt: str, quiz_id: str, image_type: str,
                              output_dir: str = "data/images") -> str:
        """
        Generate a single image for a specific purpose.
        
        Args:
            prompt: Image description
            quiz_id: The quiz this image belongs to
            image_type: Type identifier (cover, question-1, outcome-hero, etc.)
            output_dir: Base directory for images
        
        Returns:
            Relative URL path to the image
        """
        quiz_dir = Path(output_dir) / quiz_id
        
        # Determine dimensions based on type
        if image_type == "cover":
            width, height = self.cover_width, self.cover_height
        elif image_type.startswith("outcome"):
            width, height = self.outcome_width, self.outcome_height
        else:
            width, height = self.question_width, self.question_height
        
        filepath = self.generate_image(prompt, image_type, str(quiz_dir), width, height)
        
        if filepath:
            return f"/images/{quiz_id}/{image_type}.png"
        return None

    def list_available_models(self) -> list:
        """
        Fetch list of available image models from Pollinations API.
        
        Returns:
            List of model names, or empty list if request fails
        """
        try:
            url = "https://image.pollinations.ai/models"
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'QuizPlatform/1.0')
            
            if self.api_key:
                request.add_header('Authorization', f'Bearer {self.api_key}')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                models = json.loads(response.read().decode())
                return models
        except Exception as e:
            print(f"Failed to fetch models: {e}")
            return []


def main():
    """Test the image generator."""
    generator = ImageGenerator()
    
    print("=" * 50)
    print("Testing Image Generator (Pollinations API 2026)")
    print("=" * 50)
    
    if generator.api_key:
        print(f"  API Key: Configured ✓")
    else:
        print(f"  API Key: Not configured (using anonymous tier)")
        print(f"  💡 Get an API key at enter.pollinations.ai for better rate limits")
    
    # List available models
    print("\n[Available Models]")
    models = generator.list_available_models()
    if models:
        print(f"  Models: {', '.join(models[:10])}...")  # Show first 10
    else:
        print("  Could not fetch models")
    
    # Test single image generation
    print("\n[Testing Single Image]")
    test_prompt = "A magical winter scene with snowflakes and warm golden lights, cozy holiday atmosphere"
    result = generator.generate_image(
        test_prompt,
        "test-image",
        "data/images/test",
        width=800,
        height=450
    )
    
    if result:
        print(f"\nSuccess! Image saved to: {result}")
    else:
        print("\nImage generation failed.")


if __name__ == "__main__":
    main()
