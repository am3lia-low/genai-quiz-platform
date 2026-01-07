"""
Quiz Generator Module
Generates quiz content using Gemini AI based on discovered topics.
"""

import json
import re
from datetime import datetime
from pathlib import Path

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class QuizGenerator:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.gemini_client = None
        self.gemini_model = self.config['gemini']['model']
        
        if GEMINI_AVAILABLE and self.config['gemini']['api_key'] != "YOUR_GEMINI_API_KEY_HERE":
            self.gemini_client = genai.Client(api_key=self.config['gemini']['api_key'])
        else:
            print("Warning: Gemini not available. Using sample quiz data.")

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text

    def generate_personality_quiz(self, topic: str, category: str) -> dict:
        """Generate a personality quiz for the given topic."""
        settings = self.config['quiz_settings']['personality']
        num_questions = settings['questions_per_quiz']
        min_questions = settings.get('min_questions', 5)
        num_outcomes = settings['outcomes_count']

        prompt = f"""Create a fun personality quiz related to "{topic}" with exactly {num_questions} questions and {num_outcomes} possible outcomes.

IMPORTANT: You MUST generate exactly {num_questions} questions. Do not generate fewer questions.

IMPORTANT: First, decide on a creative quiz angle that makes sense for this topic. Examples:
- For "Harry Potter" → "Which Hogwarts House Do You Belong To?" (outcomes: Gryffindor, Slytherin, Ravenclaw, Hufflepuff)
- For "Harry Potter" → "What's Your Patronus?" (outcomes: Stag, Otter, Phoenix, Wolf)
- For "Greek Mythology" → "Which Greek God Are You?" (outcomes: Zeus, Athena, Poseidon, Apollo)
- For "Coffee" → "What Coffee Drink Matches Your Personality?" (outcomes: Espresso, Latte, Cold Brew, Cappuccino)
- For "Taylor Swift" → "Which Taylor Swift Era Are You?" (outcomes: Fearless, Red, 1989, Reputation)

The outcomes MUST be specific to the topic, not generic personality types like "explorer" or "introvert".

Return a valid JSON object with this exact structure:
{{
    "title": "Your creative quiz title here",
    "description": "A brief, engaging description of the quiz (1-2 sentences)",
    "questions": [
        {{
            "text": "Question text here?",
            "imagePrompt": "A detailed prompt for generating an illustration image for this question (describe scene, objects, colors, mood - NO humans, people, or faces)",
            "answers": [
                {{"text": "Answer option 1", "outcome": "outcome_id_1"}},
                {{"text": "Answer option 2", "outcome": "outcome_id_2"}},
                {{"text": "Answer option 3", "outcome": "outcome_id_3"}},
                {{"text": "Answer option 4", "outcome": "outcome_id_4"}}
            ]
        }}
    ],
    "outcomes": {{
        "outcome_id_1": {{
            "title": "Outcome Name 1",
            "description": "A fun, detailed description of this outcome that relates to the topic (2-3 sentences)",
            "imagePrompt": "A detailed prompt for generating an illustration representing this specific outcome (use symbols, objects, colors related to the topic - NO humans, people, or faces)"
        }}
    }}
}}

Requirements:
- The quiz title and outcomes MUST be specific and relevant to "{topic}"
- DO NOT use generic outcomes like "Explorer", "Homebody", "Social Butterfly", "Learner"
- Each question should have exactly 4 answer options
- Each answer maps to one of the {num_outcomes} outcomes
- Outcome IDs should be lowercase, no spaces (e.g., "gryffindor", "espresso", "stag")
- Questions should be fun, relatable, and help determine which outcome fits the user
- IMPORTANT: Image prompts must describe scenes with objects, symbols, landscapes, or abstract concepts - NEVER include humans, people, faces, or characters
- IMPORTANT: Image prompts must NOT request any text, words, letters, titles, signs, or writing - AI image generators cannot render text properly
- Make the quiz engaging and shareable

Category context: {category}

Return ONLY valid JSON, no markdown formatting or extra text."""

        if not self.gemini_client:
            return self._get_sample_personality_quiz(topic)

        try:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean up markdown formatting if present
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                text = text.rsplit('```', 1)[0]
            
            quiz_data = json.loads(text)
            
            # Validate minimum question count
            actual_questions = len(quiz_data.get('questions', []))
            if actual_questions < min_questions:
                print(f"Warning: Quiz has only {actual_questions} questions, minimum is {min_questions}. Using sample quiz.")
                return self._get_sample_personality_quiz(topic)
            
            # Add metadata
            quiz_id = self._slugify(quiz_data.get('title', f"which-{topic}-are-you"))
            quiz_data['id'] = quiz_id
            quiz_data['type'] = 'personality'
            quiz_data['category'] = category
            quiz_data['createdAt'] = datetime.now().isoformat()
            
            # Generate cover image prompt if not present - explicitly no humans and no text
            if 'coverImagePrompt' not in quiz_data:
                quiz_data['coverImagePrompt'] = f"A vibrant, eye-catching cover illustration for a quiz about {topic}, using only symbols, icons, objects, and patterns, fun and inviting style, absolutely no humans, no people, no faces, no characters, no text, no words, no letters, no writing, illustration only"
            else:
                # Ensure existing cover prompt has no-humans and no-text guidance
                quiz_data['coverImagePrompt'] = quiz_data['coverImagePrompt'] + ", absolutely no humans, no people, no faces, no characters, no text, no words, no letters, objects and symbols only"
            
            return quiz_data
        except Exception as e:
            print(f"Quiz generation error: {e}")
            return self._get_sample_personality_quiz(topic)

    def generate_trivia_quiz(self, topic: str, category: str) -> dict:
        """Generate a trivia quiz for the given topic."""
        settings = self.config['quiz_settings']['trivia']
        num_questions = settings['questions_per_quiz']
        min_questions = settings.get('min_questions', 5)
        num_options = settings['options_per_question']

        prompt = f"""Create a trivia quiz about "{topic}" with exactly {num_questions} questions, each with {num_options} options and one correct answer.

IMPORTANT: You MUST generate exactly {num_questions} questions. Do not generate fewer questions.

Return a valid JSON object with this exact structure:
{{
    "title": "{topic} Trivia Challenge",
    "description": "A brief, engaging description of the quiz (1-2 sentences)",
    "questions": [
        {{
            "text": "Question text here?",
            "imagePrompt": "A detailed prompt for generating an illustration related to this question (use objects, symbols, landscapes - NO humans, people, or faces)",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correctIndex": 0,
            "explanation": "Brief explanation of why this answer is correct"
        }}
    ]
}}

Requirements:
- Questions should range from easy to hard (progressively harder)
- Include interesting facts that people might not know
- correctIndex is 0-based (0 = first option, 3 = fourth option)
- IMPORTANT: Image prompts must describe scenes with objects, symbols, landscapes, or abstract concepts - NEVER include humans, people, faces, or characters
- IMPORTANT: Image prompts must NOT request any text, words, letters, titles, signs, or writing - AI image generators cannot render text properly
- Make questions educational but fun

Category context: {category}

Return ONLY valid JSON, no markdown formatting or extra text."""

        if not self.gemini_client:
            return self._get_sample_trivia_quiz(topic)

        try:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )
            text = response.text.strip()
            
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                text = text.rsplit('```', 1)[0]
            
            quiz_data = json.loads(text)
            
            # Validate minimum question count
            actual_questions = len(quiz_data.get('questions', []))
            if actual_questions < min_questions:
                print(f"Warning: Quiz has only {actual_questions} questions, minimum is {min_questions}. Using sample quiz.")
                return self._get_sample_trivia_quiz(topic)
            
            # Add metadata
            quiz_id = self._slugify(f"{topic}-trivia")
            quiz_data['id'] = quiz_id
            quiz_data['type'] = 'trivia'
            quiz_data['category'] = category
            quiz_data['createdAt'] = datetime.now().isoformat()
            quiz_data['coverImagePrompt'] = f"A dynamic, exciting cover illustration for a trivia quiz about {topic}, knowledge and discovery theme with books, question marks, light bulbs, and symbols, absolutely no humans, no people, no faces, no characters, no text, no words, no letters, no writing"
            
            return quiz_data
        except Exception as e:
            print(f"Quiz generation error: {e}")
            return self._get_sample_trivia_quiz(topic)

    def _get_sample_personality_quiz(self, topic: str) -> dict:
        """Return a sample personality quiz when Gemini is unavailable."""
        # Create a more topic-appropriate sample
        return {
            "id": self._slugify(f"{topic}-personality-quiz"),
            "type": "personality",
            "title": f"Which {topic} Character Are You?",
            "description": f"Discover which iconic {topic} character matches your personality!",
            "category": "sample",
            "createdAt": datetime.now().isoformat(),
            "coverImagePrompt": f"A colorful, fun cover illustration for a personality quiz about {topic}, using iconic symbols, objects, and patterns only, absolutely no humans, no people, no faces, no characters, no text, no words, no letters, no writing",
            "questions": [
                {
                    "text": "How do you approach a challenging situation?",
                    "imagePrompt": "A crossroads path in a mystical forest with different directions, each path glowing with different colors",
                    "answers": [
                        {"text": "Face it head-on with courage", "outcome": "brave"},
                        {"text": "Think it through carefully first", "outcome": "wise"},
                        {"text": "Find a creative workaround", "outcome": "clever"},
                        {"text": "Rely on my loyal friends for help", "outcome": "loyal"}
                    ]
                },
                {
                    "text": "What quality do you value most in yourself?",
                    "imagePrompt": "Four glowing gems on pedestals, each a different color representing different virtues",
                    "answers": [
                        {"text": "My bravery and determination", "outcome": "brave"},
                        {"text": "My intelligence and curiosity", "outcome": "wise"},
                        {"text": "My ambition and resourcefulness", "outcome": "clever"},
                        {"text": "My kindness and dedication", "outcome": "loyal"}
                    ]
                },
                {
                    "text": "What's your ideal way to spend a free afternoon?",
                    "imagePrompt": "A cozy room with a bookshelf, a window showing adventure outside, a chess board, and a fireplace with comfortable seating",
                    "answers": [
                        {"text": "Exploring somewhere new and exciting", "outcome": "brave"},
                        {"text": "Reading or learning something fascinating", "outcome": "wise"},
                        {"text": "Working on a personal project or goal", "outcome": "clever"},
                        {"text": "Spending quality time with loved ones", "outcome": "loyal"}
                    ]
                },
                {
                    "text": "How do your friends describe you?",
                    "imagePrompt": "Four different emblems floating in a starry sky: a lion, an owl, a fox, and a bear",
                    "answers": [
                        {"text": "Bold and adventurous", "outcome": "brave"},
                        {"text": "Thoughtful and insightful", "outcome": "wise"},
                        {"text": "Smart and ambitious", "outcome": "clever"},
                        {"text": "Caring and dependable", "outcome": "loyal"}
                    ]
                },
                {
                    "text": "What would be your dream superpower?",
                    "imagePrompt": "Magical symbols floating in space: a lightning bolt, a glowing brain, an invisibility cloak, and a protective shield",
                    "answers": [
                        {"text": "Super strength to protect others", "outcome": "brave"},
                        {"text": "Telepathy to understand everything", "outcome": "wise"},
                        {"text": "Invisibility to achieve my goals", "outcome": "clever"},
                        {"text": "Healing powers to help those I love", "outcome": "loyal"}
                    ]
                }
            ],
            "outcomes": {
                "brave": {
                    "title": "The Brave One",
                    "description": f"You embody courage and determination! In the world of {topic}, you'd be the hero charging into adventure without hesitation.",
                    "imagePrompt": "A golden shield and sword crossed over a red banner, symbolizing courage and bravery"
                },
                "wise": {
                    "title": "The Wise One",
                    "description": f"Knowledge is your greatest power! In the world of {topic}, you'd be the sage advisor everyone turns to for guidance.",
                    "imagePrompt": "An ancient tome surrounded by floating stars and a glowing crystal ball, symbolizing wisdom"
                },
                "clever": {
                    "title": "The Clever One",
                    "description": f"Your wit and cunning set you apart! In the world of {topic}, you'd be the mastermind with a plan for everything.",
                    "imagePrompt": "A silver serpent coiled around a chess piece with emerald gems, symbolizing cunning and ambition"
                },
                "loyal": {
                    "title": "The Loyal One",
                    "description": f"Your heart is your greatest strength! In the world of {topic}, you'd be the steadfast friend who never gives up.",
                    "imagePrompt": "A golden badger emblem surrounded by warm yellow flowers and honeycomb patterns, symbolizing loyalty"
                }
            }
        }

    def _get_sample_trivia_quiz(self, topic: str) -> dict:
        """Return a sample trivia quiz when Gemini is unavailable."""
        return {
            "id": self._slugify(f"{topic}-trivia"),
            "type": "trivia",
            "title": f"{topic} Trivia Challenge",
            "description": f"Test your knowledge about {topic}!",
            "category": "sample",
            "createdAt": datetime.now().isoformat(),
            "coverImagePrompt": f"An exciting trivia game show style illustration about {topic} with question marks, light bulbs, and trophy icons, absolutely no humans, no people, no faces, no characters, no text, no words, no letters, no writing",
            "questions": [
                {
                    "text": f"What is a key fact about {topic}?",
                    "imagePrompt": f"An illustration representing {topic} with relevant objects and symbols, no humans",
                    "options": ["Option A (Correct)", "Option B", "Option C", "Option D"],
                    "correctIndex": 0,
                    "explanation": "This is correct because it's the most accurate answer."
                },
                {
                    "text": f"Which of these is associated with {topic}?",
                    "imagePrompt": f"Icons and symbols related to {topic} arranged in a decorative pattern, no humans",
                    "options": ["Option A", "Option B (Correct)", "Option C", "Option D"],
                    "correctIndex": 1,
                    "explanation": "This option is most closely associated with the topic."
                },
                {
                    "text": f"When did {topic} become significant?",
                    "imagePrompt": f"A timeline with milestones and dates, decorated with symbols of {topic}, no humans",
                    "options": ["Option A", "Option B", "Option C (Correct)", "Option D"],
                    "correctIndex": 2,
                    "explanation": "This is the historically accurate timeframe."
                },
                {
                    "text": f"What makes {topic} unique?",
                    "imagePrompt": f"A spotlight shining on distinctive features of {topic}, illustrated with objects and icons, no humans",
                    "options": ["Option A", "Option B", "Option C", "Option D (Correct)"],
                    "correctIndex": 3,
                    "explanation": "This characteristic is what sets it apart from others."
                },
                {
                    "text": f"How has {topic} evolved over time?",
                    "imagePrompt": f"A visual progression showing the evolution of {topic} through symbols and objects, no humans",
                    "options": ["Option A (Correct)", "Option B", "Option C", "Option D"],
                    "correctIndex": 0,
                    "explanation": "This best describes the evolution and changes over time."
                }
            ]
        }

    def save_quiz(self, quiz: dict, output_dir: str = "data/quizzes") -> str:
        """Save the generated quiz to a JSON file."""
        quiz_type = quiz['type']
        quiz_id = quiz['id']
        
        output_path = Path(output_dir) / quiz_type / f"{quiz_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(quiz, f, indent=2)
        
        print(f"Quiz saved: {output_path}")
        return str(output_path)


def main():
    """Test the quiz generator."""
    generator = QuizGenerator()
    
    print("=" * 50)
    print("Testing Quiz Generator")
    print("=" * 50)
    
    # Generate a personality quiz
    print("\n[Generating Personality Quiz]")
    personality_quiz = generator.generate_personality_quiz("Christmas Movie Character", "movies")
    print(f"Title: {personality_quiz['title']}")
    print(f"Questions: {len(personality_quiz['questions'])}")
    print(f"Outcomes: {list(personality_quiz.get('outcomes', {}).keys())}")
    
    # Generate a trivia quiz
    print("\n[Generating Trivia Quiz]")
    trivia_quiz = generator.generate_trivia_quiz("Space Exploration", "science")
    print(f"Title: {trivia_quiz['title']}")
    print(f"Questions: {len(trivia_quiz['questions'])}")


if __name__ == "__main__":
    main()
