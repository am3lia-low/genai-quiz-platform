#!/usr/bin/env python3
"""
Quiz Pipeline Orchestrator
Main script that orchestrates the entire quiz generation pipeline.
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.trend_discovery import TrendDiscovery
from pipeline.quiz_generator import QuizGenerator
from pipeline.image_generator import ImageGenerator
from pipeline.database import Database


class QuizPipeline:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.trend_discovery = TrendDiscovery(config_path)
        self.quiz_generator = QuizGenerator(config_path)
        self.image_generator = ImageGenerator(config_path)
        self.database = Database()

    def run_full_pipeline(self, quiz_type: str, category: str,
                          topic: str = None, use_pytrends: bool = True,
                          skip_images: bool = False) -> dict:
        """
        Run the complete quiz generation pipeline.
        
        Args:
            quiz_type: 'personality' or 'trivia'
            category: Category from config (e.g., 'pop_culture', 'history')
            topic: Specific topic (optional, will discover if not provided)
            use_pytrends: Whether to try Google Trends first
            skip_images: Skip image generation for faster testing
        
        Returns:
            The generated quiz data
        """
        print("\n" + "=" * 60)
        print("🎯 QUIZ GENERATION PIPELINE")
        print("=" * 60)
        
        # Step 1: Topic Discovery (if no topic provided)
        if not topic:
            print("\n📊 Step 1: Discovering trending topics...")
            topics = self.trend_discovery.discover_topics(quiz_type, category, use_pytrends)
            
            if not topics:
                print("No topics found. Using fallback topic.")
                topic = "General Knowledge" if quiz_type == "trivia" else "Personality Types"
            else:
                # Pick the first/best topic
                topic = topics[0]['topic']
                print(f"Selected topic: {topic}")
        else:
            print(f"\n📊 Step 1: Using provided topic: {topic}")
        
        # Step 2: Generate Quiz Content
        print(f"\n✍️  Step 2: Generating {quiz_type} quiz content...")
        if quiz_type == "personality":
            quiz = self.quiz_generator.generate_personality_quiz(topic, category)
        else:
            quiz = self.quiz_generator.generate_trivia_quiz(topic, category)
        
        print(f"Generated: {quiz['title']}")
        print(f"Questions: {len(quiz['questions'])}")
        
        # Step 3: Generate Images
        if not skip_images:
            print("\n🎨 Step 3: Generating images...")
            quiz = self.image_generator.generate_quiz_images(quiz)
        else:
            print("\n🎨 Step 3: Skipping image generation")
        
        # Step 4: Save Quiz
        print("\n💾 Step 4: Saving quiz...")
        output_path = self.quiz_generator.save_quiz(quiz)
        
        # Step 5: Register in Database
        print("\n📝 Step 5: Registering quiz in database...")
        self.database.register_quiz(quiz['id'], quiz['type'], quiz['category'], quiz['title'])
        
        print("\n" + "=" * 60)
        print("✅ PIPELINE COMPLETE!")
        print("=" * 60)
        print(f"\nQuiz ID: {quiz['id']}")
        print(f"Quiz File: {output_path}")
        print(f"Type: {quiz['type']}")
        print(f"Category: {quiz['category']}")
        
        return quiz

    def generate_batch(self, count: int = 2, quiz_types: list = None,
                       skip_images: bool = False) -> list:
        """
        Generate multiple quizzes at once.
        
        Args:
            count: Number of quizzes to generate
            quiz_types: List of types to generate (default: mix of both)
            skip_images: Skip image generation
        
        Returns:
            List of generated quizzes
        """
        if quiz_types is None:
            quiz_types = ['personality', 'trivia']
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        generated = []
        
        for i in range(count):
            quiz_type = quiz_types[i % len(quiz_types)]
            categories = config['categories'][quiz_type]
            category = categories[i % len(categories)]
            
            print(f"\n\n{'#' * 60}")
            print(f"# Generating Quiz {i+1} of {count}")
            print(f"{'#' * 60}")
            
            try:
                quiz = self.run_full_pipeline(
                    quiz_type=quiz_type,
                    category=category,
                    skip_images=skip_images
                )
                generated.append(quiz)
            except Exception as e:
                print(f"Error generating quiz: {e}")
                continue
        
        return generated

    def list_quizzes(self) -> list:
        """List all generated quizzes."""
        return self.database.get_all_quizzes()


def main():
    parser = argparse.ArgumentParser(description="Quiz Generation Pipeline")
    parser.add_argument('--type', '-t', choices=['personality', 'trivia'],
                        help='Quiz type to generate')
    parser.add_argument('--category', '-c', help='Quiz category')
    parser.add_argument('--topic', help='Specific topic (optional)')
    parser.add_argument('--batch', '-b', type=int, default=1,
                        help='Number of quizzes to generate')
    parser.add_argument('--skip-images', action='store_true',
                        help='Skip image generation')
    parser.add_argument('--no-pytrends', action='store_true',
                        help='Skip Google Trends, use Gemini only')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all generated quizzes')
    
    args = parser.parse_args()
    
    pipeline = QuizPipeline()
    
    if args.list:
        print("\n📋 Generated Quizzes:")
        print("-" * 50)
        quizzes = pipeline.list_quizzes()
        if not quizzes:
            print("No quizzes generated yet.")
        for q in quizzes:
            print(f"  [{q['type']}] {q['title']}")
            print(f"         ID: {q['id']} | Plays: {q['play_count']}")
        return
    
    if args.batch > 1:
        quiz_types = [args.type] if args.type else None
        pipeline.generate_batch(
            count=args.batch,
            quiz_types=quiz_types,
            skip_images=args.skip_images
        )
    else:
        # Default values if not specified
        quiz_type = args.type or 'personality'
        category = args.category or 'pop_culture'
        
        pipeline.run_full_pipeline(
            quiz_type=quiz_type,
            category=category,
            topic=args.topic,
            use_pytrends=not args.no_pytrends,
            skip_images=args.skip_images
        )


if __name__ == "__main__":
    main()
