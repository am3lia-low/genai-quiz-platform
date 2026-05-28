#!/usr/bin/env python3
"""
Manual Quiz Generator
Generate quizzes by specifying topics directly - no pytrends needed!
"""

import json
import sys
import os
from pathlib import Path

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.quiz_generator import QuizGenerator
from pipeline.image_generator import ImageGenerator
from pipeline.database import Database


def generate_quiz(topic: str, quiz_type: str = "personality", category: str = "pop_culture"):
    """
    Generate a single quiz for a given topic.
    
    Args:
        topic: The quiz topic (e.g., "Harry Potter", "Coffee", "Taylor Swift")
        quiz_type: "personality" or "trivia"
        category: Category for organization
    """
    print(f"\n{'='*60}")
    print(f"Generating {quiz_type} quiz about: {topic}")
    print(f"{'='*60}")
    
    # Initialize generators
    quiz_gen = QuizGenerator()
    image_gen = ImageGenerator()
    
    # Generate quiz content
    print("\n[Step 1/3] Generating quiz content with Gemini...")
    if quiz_type == "personality":
        quiz = quiz_gen.generate_personality_quiz(topic, category)
    else:
        quiz = quiz_gen.generate_trivia_quiz(topic, category)
    
    print(f"  OK Generated: {quiz['title']}")
    print(f"  OK Questions: {len(quiz['questions'])}")
    if quiz_type == "personality":
        print(f"  OK Outcomes: {len(quiz.get('outcomes', {}))}")
    
    # Generate images
    print("\n[Step 2/3] Generating images...")
    quiz = image_gen.generate_quiz_images(quiz)
    
    # Save quiz JSON
    print("\n[Step 3/3] Saving quiz data...")
    quiz_file = quiz_gen.save_quiz(quiz)
    print(f"  OK Saved: {quiz_file}")
    
    # Update quiz index
    update_quiz_index(quiz)
    Database().register_quiz(quiz['id'], quiz['type'], quiz['category'], quiz['title'])
    
    print(f"\n{'='*60}")
    print(f"Quiz generated successfully!")
    print(f"   ID: {quiz['id']}")
    print(f"   File: {quiz_file}")
    print(f"{'='*60}\n")
    
    return quiz


def update_quiz_index(quiz: dict):
    """Add the quiz to the main index file."""
    index_file = Path("data/quizzes/index.json")
    
    # Load existing index or create new
    if index_file.exists():
        with open(index_file, 'r') as f:
            index = json.load(f)
    else:
        index = {"quizzes": []}
    
    # Check if quiz already exists (update it)
    existing_ids = [q['id'] for q in index['quizzes']]
    if quiz['id'] in existing_ids:
        # Update existing
        for i, q in enumerate(index['quizzes']):
            if q['id'] == quiz['id']:
                index['quizzes'][i] = {
                    "id": quiz['id'],
                    "title": quiz['title'],
                    "description": quiz.get('description', ''),
                    "type": quiz['type'],
                    "category": quiz.get('category', 'general'),
                    "coverImage": quiz.get('coverImage', ''),
                    "questionCount": len(quiz['questions']),
                    "createdAt": quiz.get('createdAt', '')
                }
                break
    else:
        # Add new
        index['quizzes'].insert(0, {
            "id": quiz['id'],
            "title": quiz['title'],
            "description": quiz.get('description', ''),
            "type": quiz['type'],
            "category": quiz.get('category', 'general'),
            "coverImage": quiz.get('coverImage', ''),
            "questionCount": len(quiz['questions']),
            "createdAt": quiz.get('createdAt', '')
        })
    
    # Save index
    with open(index_file, 'w') as f:
        json.dump(index, f, indent=2)
    print(f"  OK Updated index: {index_file}")


def list_quizzes():
    """List all generated quizzes."""
    base_path = Path("data/quizzes")
    quizzes = []

    for quiz_type in ("personality", "trivia"):
        type_path = base_path / quiz_type
        if not type_path.exists():
            continue

        for quiz_file in type_path.glob("*.json"):
            try:
                with open(quiz_file, 'r') as f:
                    quiz = json.load(f)
                quizzes.append({
                    "id": quiz["id"],
                    "title": quiz["title"],
                    "type": quiz["type"],
                    "category": quiz.get("category", "general"),
                    "questionCount": len(quiz.get("questions", [])),
                    "createdAt": quiz.get("createdAt", "")
                })
            except Exception as e:
                print(f"Skipping invalid quiz file {quiz_file}: {e}")

    quizzes.sort(key=lambda quiz: quiz.get("createdAt", ""), reverse=True)

    if not quizzes:
        print("No quizzes generated yet!")
        return

    index = {"quizzes": quizzes}

    print(f"\n{'='*60}")
    print(f"Generated Quizzes ({len(index['quizzes'])} total)")
    print(f"{'='*60}\n")
    
    for i, quiz in enumerate(quizzes, 1):
        print(f"{i}. [{quiz['type'].upper()}] {quiz['title']}")
        print(f"   ID: {quiz['id']}")
        print(f"   Category: {quiz['category']} | Questions: {quiz['questionCount']}")
        print()


def interactive_mode():
    """Run in interactive mode - prompt user for input."""
    print("""
============================================================
QUIZ GENERATOR - Interactive Mode
============================================================
Commands:
  generate  - Create a new quiz
  list      - Show all quizzes
  quit      - Exit
============================================================
""")
    
    while True:
        command = input("\n> Enter command: ").strip().lower()
        
        if command == "quit" or command == "exit" or command == "q":
            print("Goodbye!")
            break
            
        elif command == "list" or command == "ls":
            list_quizzes()
            
        elif command == "generate" or command == "gen" or command == "new":
            # Get topic
            topic = input("  Topic (e.g., 'Harry Potter', 'Coffee'): ").strip()
            if not topic:
                print("  Error: Topic cannot be empty!")
                continue
            
            # Get quiz type
            quiz_type = input("  Type [personality/trivia] (default: personality): ").strip().lower()
            if quiz_type not in ["personality", "trivia"]:
                quiz_type = "personality"
            
            # Get category
            print("  Categories: pop_culture, movies, food, travel, mythology, sports, science, history")
            category = input("  Category (default: pop_culture): ").strip().lower()
            if not category:
                category = "pop_culture"
            
            # Generate!
            try:
                generate_quiz(topic, quiz_type, category)
            except Exception as e:
                print(f"  Error generating quiz: {e}")
        
        else:
            print("  Unknown command. Try: generate, list, or quit")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # No arguments - run interactive mode
        interactive_mode()
    
    elif sys.argv[1] == "list":
        list_quizzes()
    
    elif sys.argv[1] == "generate" or sys.argv[1] == "gen":
        if len(sys.argv) < 3:
            print("Usage: python generate_quiz.py generate <topic> [type] [category]")
            print("  Example: python generate_quiz.py generate 'Harry Potter' personality movies")
            sys.exit(1)
        
        topic = sys.argv[2]
        quiz_type = sys.argv[3] if len(sys.argv) > 3 else "personality"
        category = sys.argv[4] if len(sys.argv) > 4 else "pop_culture"
        
        generate_quiz(topic, quiz_type, category)
    
    else:
        print("""
Usage: python generate_quiz.py [command] [options]

Commands:
  (no args)     Run interactive mode
  list          List all generated quizzes
  generate      Generate a quiz
  
Examples:
  python generate_quiz.py
  python generate_quiz.py list
  python generate_quiz.py generate "Harry Potter" personality movies
  python generate_quiz.py generate "World Geography" trivia geography
""")


if __name__ == "__main__":
    main()
