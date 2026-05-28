"""
Quiz Generator Module
Generates planned, validated quiz content using Gemini AI.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline.api_keys import GeminiClientPool, get_gemini_api_keys

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


QUALITY_PROFILES = {"economy", "standard", "editorial"}


class QuizGenerator:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.gemini_client = None
        self.default_model = self.config.get('gemini', {}).get('model', 'gemini-2.5-flash')
        self.gemini_keys = get_gemini_api_keys(self.config)

        if GEMINI_AVAILABLE and self.gemini_keys:
            self.gemini_client = GeminiClientPool(
                self.gemini_keys,
                lambda api_key: genai.Client(api_key=api_key)
            )
        else:
            print("Warning: Gemini not available. Using sample quiz data.")

    def _slugify(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text

    def _model_for(self, role: str, quality: str = "standard") -> str:
        quality = quality if quality in QUALITY_PROFILES else "standard"
        models = self.config.get('models', {})

        if quality == "editorial":
            return models.get(f"editorial_{role}") or models.get("fallback_planner") or "gemini-2.5-pro"

        if role == "fallback_planner":
            return models.get("fallback_planner") or "gemini-2.5-pro"

        return models.get(role) or self.default_model

    def _bounds(self, quiz_type: str) -> dict:
        settings = self.config['quiz_settings'][quiz_type]

        if quiz_type == "personality":
            fixed_questions = settings.get('questions_per_quiz', 7)
            fixed_outcomes = settings.get('outcomes_count', 4)
            fixed_options = settings.get('options_per_question', 4)
            return {
                "fixed_questions": fixed_questions,
                "fixed_outcomes": fixed_outcomes,
                "fixed_options": fixed_options,
                "min_questions": settings.get('min_questions', 5),
                "max_questions": settings.get('max_questions', max(10, fixed_questions)),
                "min_outcomes": settings.get('min_outcomes', 3),
                "max_outcomes": settings.get('max_outcomes', max(6, fixed_outcomes)),
                "min_options": settings.get('min_options_per_question', 3),
                "max_options": settings.get('max_options_per_question', max(5, fixed_options)),
            }

        fixed_questions = settings.get('questions_per_quiz', 10)
        fixed_options = settings.get('options_per_question', 4)
        return {
            "fixed_questions": fixed_questions,
            "fixed_options": fixed_options,
            "min_questions": settings.get('min_questions', 6),
            "max_questions": settings.get('max_questions', max(12, fixed_questions)),
            "min_options": settings.get('min_options_per_question', 3),
            "max_options": settings.get('max_options_per_question', max(5, fixed_options)),
        }

    def _schema_for_plan(self, quiz_type: str) -> dict:
        base_properties = {
            "quizAngle": {"type": "string"},
            "questionCount": {"type": "integer"},
            "optionsPerQuestion": {"type": "integer"},
            "scoringStyle": {"type": "string"},
            "imageStyle": {"type": "string"},
            "titleDirection": {"type": "string"},
            "descriptionDirection": {"type": "string"},
        }

        if quiz_type == "personality":
            base_properties.update({
                "outcomeCount": {"type": "integer"},
                "outcomes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["id", "title", "description"],
                    },
                },
            })
            required = [
                "quizAngle", "questionCount", "optionsPerQuestion", "outcomeCount",
                "outcomes", "scoringStyle", "imageStyle", "titleDirection", "descriptionDirection"
            ]
        else:
            required = [
                "quizAngle", "questionCount", "optionsPerQuestion",
                "scoringStyle", "imageStyle", "titleDirection", "descriptionDirection"
            ]

        return {"type": "object", "properties": base_properties, "required": required}

    def _schema_for_quiz(self, quiz_type: str) -> dict:
        common = {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "coverImagePrompt": {"type": "string"},
            "stockSearchQuery": {"type": "string"},
        }

        if quiz_type == "personality":
            common.update({
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "imagePrompt": {"type": "string"},
                            "answers": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "outcome": {"type": "string"},
                                    },
                                    "required": ["text", "outcome"],
                                },
                            },
                        },
                        "required": ["text", "imagePrompt", "answers"],
                    },
                },
                "outcomes": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "imagePrompt": {"type": "string"},
                            "stockSearchQuery": {"type": "string"},
                        },
                        "required": ["title", "description", "imagePrompt"],
                    },
                },
            })
            required = ["title", "description", "coverImagePrompt", "questions", "outcomes"]
        else:
            common.update({
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "imagePrompt": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "correctIndex": {"type": "integer"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["text", "imagePrompt", "options", "correctIndex", "explanation"],
                    },
                },
            })
            required = ["title", "description", "coverImagePrompt", "questions"]

        return {"type": "object", "properties": common, "required": required}

    def _parse_response(self, response: Any) -> dict:
        parsed = getattr(response, "parsed", None)
        if parsed:
            if hasattr(parsed, "model_dump"):
                return parsed.model_dump()
            if isinstance(parsed, dict):
                return parsed

        text = response.text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            text = text.rsplit('```', 1)[0]
        return json.loads(text)

    def _generate_structured(self, prompt: str, schema: dict, model: str) -> dict:
        response = self.gemini_client.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                responseMimeType="application/json",
                responseJsonSchema=schema,
                temperature=0.8,
            ),
        )
        return self._parse_response(response)

    def _fixed_plan(self, quiz_type: str, topic: str, category: str) -> dict:
        bounds = self._bounds(quiz_type)
        plan = {
            "quizAngle": f"{topic} Trivia Challenge" if quiz_type == "trivia" else f"Which {topic} Match Are You?",
            "questionCount": bounds["fixed_questions"],
            "optionsPerQuestion": bounds["fixed_options"],
            "scoringStyle": "correct_answer_score" if quiz_type == "trivia" else "balanced_outcome_mapping",
            "imageStyle": "bright, object-and-symbol based quiz illustrations with no people and no text",
            "titleDirection": f"Create an engaging {quiz_type} quiz title about {topic}.",
            "descriptionDirection": "Write a brief, playful, shareable quiz description.",
            "topic": topic,
            "category": category,
            "type": quiz_type,
            "shapeMode": "fixed",
        }

        if quiz_type == "personality":
            sample = self._get_sample_personality_quiz(topic)
            outcomes = [
                {"id": outcome_id, "title": outcome["title"], "description": outcome["description"]}
                for outcome_id, outcome in list(sample["outcomes"].items())[:bounds["fixed_outcomes"]]
            ]
            plan["outcomeCount"] = len(outcomes)
            plan["outcomes"] = outcomes

        return plan

    def _fallback_plan(self, quiz_type: str, topic: str, category: str) -> dict:
        plan = self._fixed_plan(quiz_type, topic, category)
        plan["shapeMode"] = "fallback"
        if quiz_type == "personality":
            bounds = self._bounds(quiz_type)
            plan["questionCount"] = max(bounds["min_questions"], min(7, bounds["max_questions"]))
            plan["optionsPerQuestion"] = max(bounds["min_options"], min(4, bounds["max_options"]))
        return plan

    def _normalize_plan(self, plan: dict, quiz_type: str, topic: str, category: str, shape: str) -> dict:
        bounds = self._bounds(quiz_type)
        plan["type"] = quiz_type
        plan["topic"] = topic
        plan["category"] = category
        plan["shapeMode"] = shape
        plan["questionCount"] = int(plan.get("questionCount", bounds["fixed_questions"]))
        plan["optionsPerQuestion"] = int(plan.get("optionsPerQuestion", bounds["fixed_options"]))

        if shape == "fixed":
            plan["questionCount"] = bounds["fixed_questions"]
            plan["optionsPerQuestion"] = bounds["fixed_options"]
        else:
            plan["questionCount"] = max(bounds["min_questions"], min(plan["questionCount"], bounds["max_questions"]))
            plan["optionsPerQuestion"] = max(bounds["min_options"], min(plan["optionsPerQuestion"], bounds["max_options"]))

        if quiz_type == "personality":
            outcomes = plan.get("outcomes") or []
            normalized = []
            seen = set()
            for outcome in outcomes:
                outcome_id = self._slugify(outcome.get("id") or outcome.get("title", "outcome"))
                if outcome_id and outcome_id not in seen:
                    seen.add(outcome_id)
                    normalized.append({
                        "id": outcome_id,
                        "title": outcome.get("title") or outcome_id.replace("-", " ").title(),
                        "description": outcome.get("description") or f"A distinct {topic} outcome.",
                    })

            if shape == "fixed":
                target = bounds["fixed_outcomes"]
            else:
                target = max(bounds["min_outcomes"], min(len(normalized), bounds["max_outcomes"]))

            if len(normalized) < target:
                sample_outcomes = self._fallback_plan("personality", topic, category)["outcomes"]
                for outcome in sample_outcomes:
                    if len(normalized) >= target:
                        break
                    if outcome["id"] not in seen:
                        seen.add(outcome["id"])
                        normalized.append(outcome)

            plan["outcomes"] = normalized[:target]
            plan["outcomeCount"] = len(plan["outcomes"])

        return plan

    def generate_quiz_plan(self, quiz_type: str, topic: str, category: str,
                           shape: str = "auto", quality: str = "standard") -> dict:
        """Generate or derive the quiz shape before content generation."""
        if shape == "fixed":
            return self._fixed_plan(quiz_type, topic, category)

        if not self.gemini_client:
            return self._fallback_plan(quiz_type, topic, category)

        bounds = self._bounds(quiz_type)
        prompt = f"""Plan a {quiz_type} quiz about "{topic}" in category "{category}".

Choose a quiz shape that fits the topic, but stay inside these bounds:
- Questions: {bounds['min_questions']} to {bounds['max_questions']}
- Options per question: {bounds['min_options']} to {bounds['max_options']}
"""
        if quiz_type == "personality":
            prompt += f"""- Outcomes: {bounds['min_outcomes']} to {bounds['max_outcomes']}

For personality quizzes, outcomes must be specific to the topic and suitable for balanced answer mapping.
Avoid generic outcomes like Explorer, Introvert, Leader, or Dreamer unless the topic truly requires them.
"""
        else:
            prompt += "\nFor trivia quizzes, use correct_answer_score as the scoring style.\n"

        prompt += "\nReturn only the requested JSON object."

        models_to_try = [self._model_for("planner", quality)]
        if quality == "standard":
            models_to_try.append(self._model_for("fallback_planner", quality))

        last_error = None
        for model in models_to_try:
            try:
                plan = self._generate_structured(prompt, self._schema_for_plan(quiz_type), model)
                return self._normalize_plan(plan, quiz_type, topic, category, shape)
            except Exception as e:
                last_error = e
                print(f"Plan generation failed with {model}: {e}")

        print(f"Warning: Using fallback quiz plan after plan generation failed: {last_error}")
        return self._fallback_plan(quiz_type, topic, category)

    def _personality_prompt(self, topic: str, category: str, plan: dict) -> str:
        outcomes_json = json.dumps(plan["outcomes"], indent=2)
        return f"""Create the full personality quiz content for this approved plan.

Topic: {topic}
Category: {category}
Quiz angle: {plan['quizAngle']}
Question count: {plan['questionCount']}
Options per question: {plan['optionsPerQuestion']}
Scoring style: {plan['scoringStyle']}
Image style: {plan['imageStyle']}
Outcomes:
{outcomes_json}

Rules:
- Generate exactly {plan['questionCount']} questions.
- Each question must have exactly {plan['optionsPerQuestion']} answers.
- Every answer outcome must use one of the approved outcome ids.
- Distribute outcomes as evenly as possible across the full quiz.
- Questions should feel specific to the topic and suitable for a shareable quiz.
- Image prompts must describe objects, symbols, scenes, colors, and mood.
- Image prompts must not request humans, people, faces, characters, text, letters, signs, or writing.
- Return only JSON matching the schema."""

    def _trivia_prompt(self, topic: str, category: str, plan: dict) -> str:
        return f"""Create the full trivia quiz content for this approved plan.

Topic: {topic}
Category: {category}
Quiz angle: {plan['quizAngle']}
Question count: {plan['questionCount']}
Options per question: {plan['optionsPerQuestion']}
Scoring style: {plan['scoringStyle']}
Image style: {plan['imageStyle']}

Rules:
- Generate exactly {plan['questionCount']} questions.
- Each question must have exactly {plan['optionsPerQuestion']} options.
- correctIndex must be a zero-based integer that points to the correct option.
- Questions should progress from easier to harder.
- Explanations should be concise and educational.
- Image prompts must describe objects, symbols, scenes, colors, and mood.
- Image prompts must not request humans, people, faces, characters, text, letters, signs, or writing.
- Return only JSON matching the schema."""

    def _add_metadata(self, quiz_data: dict, quiz_type: str, topic: str, category: str, plan: dict) -> dict:
        if quiz_type == "personality":
            quiz_id = self._slugify(quiz_data.get('title', f"which-{topic}-are-you"))
        else:
            quiz_id = self._slugify(quiz_data.get('title', f"{topic}-trivia"))

        quiz_data['id'] = quiz_id
        quiz_data['type'] = quiz_type
        quiz_data['category'] = category
        quiz_data['createdAt'] = datetime.now().isoformat()
        quiz_data['generationPlan'] = plan
        quiz_data.setdefault('stockSearchQuery', f"{topic} trivia knowledge" if quiz_type == "trivia" else topic)
        quiz_data.setdefault(
            'coverImagePrompt',
            f"A vibrant quiz cover about {topic}, objects and symbols only, no humans, no people, no faces, no text"
        )

        if quiz_type == "personality":
            for outcome_id, outcome in quiz_data.get('outcomes', {}).items():
                outcome.setdefault('stockSearchQuery', f"{topic} {outcome.get('title', outcome_id)}")

        return quiz_data

    def _validate_quiz(self, quiz_data: dict, quiz_type: str, plan: dict) -> None:
        questions = quiz_data.get("questions", [])
        if len(questions) != plan["questionCount"]:
            raise ValueError(f"Expected {plan['questionCount']} questions, got {len(questions)}")

        if quiz_type == "personality":
            outcomes = quiz_data.get("outcomes", {})
            expected_ids = {outcome["id"] for outcome in plan["outcomes"]}
            if set(outcomes.keys()) != expected_ids:
                raise ValueError("Personality outcomes do not match the approved plan")

            used_outcomes = set()
            for index, question in enumerate(questions):
                answers = question.get("answers", [])
                if len(answers) != plan["optionsPerQuestion"]:
                    raise ValueError(f"Question {index + 1} has an invalid answer count")
                for answer in answers:
                    outcome_id = answer.get("outcome")
                    if outcome_id not in expected_ids:
                        raise ValueError(f"Question {index + 1} uses invalid outcome {outcome_id}")
                    used_outcomes.add(outcome_id)

            if used_outcomes != expected_ids:
                raise ValueError("Not every planned outcome is used by the answers")
            return

        for index, question in enumerate(questions):
            options = question.get("options", [])
            correct_index = question.get("correctIndex")
            if len(options) != plan["optionsPerQuestion"]:
                raise ValueError(f"Question {index + 1} has an invalid option count")
            if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options):
                raise ValueError(f"Question {index + 1} has an invalid correctIndex")

    def _generate_quiz_from_plan(self, quiz_type: str, topic: str, category: str,
                                 plan: dict, quality: str = "standard") -> dict:
        if not self.gemini_client:
            return self._sample_from_plan(quiz_type, topic, category, plan)

        prompt = (
            self._personality_prompt(topic, category, plan)
            if quiz_type == "personality"
            else self._trivia_prompt(topic, category, plan)
        )

        model = self._model_for("generator", quality)
        try:
            quiz_data = self._generate_structured(prompt, self._schema_for_quiz(quiz_type), model)
            self._validate_quiz(quiz_data, quiz_type, plan)
            return self._add_metadata(quiz_data, quiz_type, topic, category, plan)
        except Exception as e:
            print(f"Quiz generation error: {e}")
            return self._sample_from_plan(quiz_type, topic, category, plan)

    def _sample_from_plan(self, quiz_type: str, topic: str, category: str, plan: dict) -> dict:
        if quiz_type == "personality":
            quiz = self._get_sample_personality_quiz(topic)
            planned_outcomes = plan.get("outcomes") or []
            if planned_outcomes:
                quiz["outcomes"] = {
                    outcome["id"]: {
                        "title": outcome["title"],
                        "description": outcome["description"],
                        "imagePrompt": f"Symbolic illustration for {outcome['title']} in a quiz about {topic}, no humans, no text",
                        "stockSearchQuery": f"{topic} {outcome['title']}",
                    }
                    for outcome in planned_outcomes
                }

            outcome_ids = list(quiz["outcomes"].keys())
            question_templates = quiz["questions"]
            questions = []
            for index in range(plan["questionCount"]):
                template = question_templates[index % len(question_templates)]
                answers = []
                for option_index in range(plan["optionsPerQuestion"]):
                    outcome_id = outcome_ids[(index + option_index) % len(outcome_ids)]
                    answers.append({
                        "text": f"{template['answers'][option_index % len(template['answers'])]['text']}",
                        "outcome": outcome_id,
                    })
                questions.append({
                    "text": template["text"],
                    "imagePrompt": template["imagePrompt"],
                    "answers": answers,
                })
            quiz["questions"] = questions
        else:
            quiz = self._get_sample_trivia_quiz(topic)
            question_templates = quiz["questions"]
            questions = []
            for index in range(plan["questionCount"]):
                template = question_templates[index % len(question_templates)]
                options = list(template["options"])
                while len(options) < plan["optionsPerQuestion"]:
                    options.append(f"Option {chr(65 + len(options))}")
                options = options[:plan["optionsPerQuestion"]]
                correct_index = min(template["correctIndex"], len(options) - 1)
                questions.append({
                    "text": template["text"],
                    "imagePrompt": template["imagePrompt"],
                    "options": options,
                    "correctIndex": correct_index,
                    "explanation": template["explanation"],
                })
            quiz["questions"] = questions

        quiz["category"] = category
        quiz["generationPlan"] = plan
        return quiz

    def generate_personality_quiz(self, topic: str, category: str,
                                  plan: dict | None = None, shape: str = "auto",
                                  quality: str = "standard") -> dict:
        plan = plan or self.generate_quiz_plan("personality", topic, category, shape, quality)
        return self._generate_quiz_from_plan("personality", topic, category, plan, quality)

    def generate_trivia_quiz(self, topic: str, category: str,
                             plan: dict | None = None, shape: str = "auto",
                             quality: str = "standard") -> dict:
        plan = plan or self.generate_quiz_plan("trivia", topic, category, shape, quality)
        return self._generate_quiz_from_plan("trivia", topic, category, plan, quality)

    def _get_sample_personality_quiz(self, topic: str) -> dict:
        return {
            "id": self._slugify(f"{topic}-personality-quiz"),
            "type": "personality",
            "title": f"Which {topic} Character Are You?",
            "description": f"Discover which iconic {topic} character matches your personality!",
            "category": "sample",
            "createdAt": datetime.now().isoformat(),
            "coverImagePrompt": f"A colorful quiz cover about {topic}, iconic symbols and patterns only, no humans, no people, no faces, no text",
            "stockSearchQuery": topic,
            "questions": [
                {
                    "text": "How do you approach a challenging situation?",
                    "imagePrompt": "A crossroads path in a mystical forest with different glowing directions",
                    "answers": [
                        {"text": "Face it head-on with courage", "outcome": "brave"},
                        {"text": "Think it through carefully first", "outcome": "wise"},
                        {"text": "Find a creative workaround", "outcome": "clever"},
                        {"text": "Rely on trusted support", "outcome": "loyal"},
                    ],
                },
                {
                    "text": "What quality do you value most in yourself?",
                    "imagePrompt": "Four glowing gems on pedestals, each a different color representing virtues",
                    "answers": [
                        {"text": "Bravery and determination", "outcome": "brave"},
                        {"text": "Intelligence and curiosity", "outcome": "wise"},
                        {"text": "Ambition and resourcefulness", "outcome": "clever"},
                        {"text": "Kindness and dedication", "outcome": "loyal"},
                    ],
                },
                {
                    "text": "What's your ideal way to spend a free afternoon?",
                    "imagePrompt": "A cozy room with books, a window to adventure, a chess board, and warm light",
                    "answers": [
                        {"text": "Exploring somewhere new", "outcome": "brave"},
                        {"text": "Learning something fascinating", "outcome": "wise"},
                        {"text": "Working on a personal goal", "outcome": "clever"},
                        {"text": "Spending time with loved ones", "outcome": "loyal"},
                    ],
                },
                {
                    "text": "How do others usually describe you?",
                    "imagePrompt": "Four symbolic emblems floating in a starry sky",
                    "answers": [
                        {"text": "Bold and adventurous", "outcome": "brave"},
                        {"text": "Thoughtful and insightful", "outcome": "wise"},
                        {"text": "Smart and strategic", "outcome": "clever"},
                        {"text": "Caring and dependable", "outcome": "loyal"},
                    ],
                },
                {
                    "text": "What kind of power would you choose?",
                    "imagePrompt": "Magical symbols floating in space: lightning, a glowing mind, a cloak, and a shield",
                    "answers": [
                        {"text": "Strength to protect others", "outcome": "brave"},
                        {"text": "Insight to understand anything", "outcome": "wise"},
                        {"text": "Stealth to reach my goals", "outcome": "clever"},
                        {"text": "Healing to help others", "outcome": "loyal"},
                    ],
                },
            ],
            "outcomes": {
                "brave": {
                    "title": "The Brave One",
                    "description": f"You bring courage and momentum to the world of {topic}.",
                    "imagePrompt": "A golden shield and sword over a red banner, courage and bravery",
                },
                "wise": {
                    "title": "The Wise One",
                    "description": f"You bring insight and patience to the world of {topic}.",
                    "imagePrompt": "An ancient book surrounded by stars and a glowing crystal, wisdom",
                },
                "clever": {
                    "title": "The Clever One",
                    "description": f"You bring strategy and wit to the world of {topic}.",
                    "imagePrompt": "A silver fox emblem beside chess pieces and emerald light, clever strategy",
                },
                "loyal": {
                    "title": "The Loyal One",
                    "description": f"You bring warmth and dedication to the world of {topic}.",
                    "imagePrompt": "A warm golden emblem surrounded by flowers and linked circles, loyalty",
                },
            },
        }

    def _get_sample_trivia_quiz(self, topic: str) -> dict:
        return {
            "id": self._slugify(f"{topic}-trivia"),
            "type": "trivia",
            "title": f"{topic} Trivia Challenge",
            "description": f"Test your knowledge about {topic}!",
            "category": "sample",
            "createdAt": datetime.now().isoformat(),
            "coverImagePrompt": f"An exciting trivia cover about {topic} with symbolic objects and trophy icons, no humans, no text",
            "stockSearchQuery": f"{topic} trivia knowledge",
            "questions": [
                {
                    "text": f"What is a key fact about {topic}?",
                    "imagePrompt": f"An illustration representing {topic} with relevant objects and symbols, no humans",
                    "options": ["Option A (Correct)", "Option B", "Option C", "Option D"],
                    "correctIndex": 0,
                    "explanation": "This is correct because it is the most accurate answer.",
                },
                {
                    "text": f"Which of these is associated with {topic}?",
                    "imagePrompt": f"Icons and symbols related to {topic} arranged in a decorative pattern, no humans",
                    "options": ["Option A", "Option B (Correct)", "Option C", "Option D"],
                    "correctIndex": 1,
                    "explanation": "This option is most closely associated with the topic.",
                },
                {
                    "text": f"When did {topic} become significant?",
                    "imagePrompt": f"A symbolic timeline decorated with objects related to {topic}, no humans",
                    "options": ["Option A", "Option B", "Option C (Correct)", "Option D"],
                    "correctIndex": 2,
                    "explanation": "This is the historically accurate timeframe.",
                },
                {
                    "text": f"What makes {topic} unique?",
                    "imagePrompt": f"A spotlight shining on distinctive symbolic features of {topic}, no humans",
                    "options": ["Option A", "Option B", "Option C", "Option D (Correct)"],
                    "correctIndex": 3,
                    "explanation": "This characteristic is what sets it apart.",
                },
                {
                    "text": f"How has {topic} evolved over time?",
                    "imagePrompt": f"A visual progression showing the evolution of {topic} through symbols and objects, no humans",
                    "options": ["Option A (Correct)", "Option B", "Option C", "Option D"],
                    "correctIndex": 0,
                    "explanation": "This best describes the evolution and changes over time.",
                },
            ],
        }

    def save_quiz(self, quiz: dict, output_dir: str = "data/quizzes") -> str:
        quiz_type = quiz['type']
        quiz_id = quiz['id']

        output_path = Path(output_dir) / quiz_type / f"{quiz_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(quiz, f, indent=2)

        print(f"Quiz saved: {output_path}")
        return str(output_path)


def main():
    generator = QuizGenerator()

    print("=" * 50)
    print("Testing Quiz Generator")
    print("=" * 50)

    personality_plan = generator.generate_quiz_plan("personality", "Christmas Movie Character", "movies")
    personality_quiz = generator.generate_personality_quiz(
        "Christmas Movie Character", "movies", plan=personality_plan
    )
    print(f"Personality title: {personality_quiz['title']}")
    print(f"Questions: {len(personality_quiz['questions'])}")

    trivia_plan = generator.generate_quiz_plan("trivia", "Space Exploration", "science")
    trivia_quiz = generator.generate_trivia_quiz("Space Exploration", "science", plan=trivia_plan)
    print(f"Trivia title: {trivia_quiz['title']}")
    print(f"Questions: {len(trivia_quiz['questions'])}")


if __name__ == "__main__":
    main()
