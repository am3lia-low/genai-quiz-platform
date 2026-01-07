"""
Database Module
Handles SQLite database operations for storing user quiz responses.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: str = "data/responses.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create responses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                id TEXT PRIMARY KEY,
                quiz_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                answers TEXT NOT NULL,
                outcome TEXT,
                score INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index for faster quiz lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_quiz_id ON responses(quiz_id)
        ''')
        
        # Create quizzes metadata table (for tracking generated quizzes)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                play_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()

    def save_response(self, quiz_id: str, user_name: str, answers: list,
                      outcome: Optional[str] = None, score: Optional[int] = None) -> str:
        """
        Save a user's quiz response.
        
        Args:
            quiz_id: The quiz identifier
            user_name: User's display name
            answers: List of answer choices/indices
            outcome: Personality quiz outcome (optional)
            score: Trivia quiz score (optional)
        
        Returns:
            The response ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        response_id = str(uuid.uuid4())[:8]
        answers_json = json.dumps(answers)
        
        cursor.execute('''
            INSERT INTO responses (id, quiz_id, user_name, answers, outcome, score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (response_id, quiz_id, user_name, answers_json, outcome, score))
        
        # Increment play count
        cursor.execute('''
            UPDATE quizzes SET play_count = play_count + 1 WHERE id = ?
        ''', (quiz_id,))
        
        conn.commit()
        conn.close()
        
        return response_id

    def get_quiz_stats(self, quiz_id: str) -> dict:
        """
        Get aggregate statistics for a quiz.
        
        Args:
            quiz_id: The quiz identifier
        
        Returns:
            Dictionary with stats (total plays, outcome distribution, avg score)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total responses
        cursor.execute('SELECT COUNT(*) FROM responses WHERE quiz_id = ?', (quiz_id,))
        total = cursor.fetchone()[0]
        
        # Outcome distribution (for personality quizzes)
        cursor.execute('''
            SELECT outcome, COUNT(*) as count
            FROM responses
            WHERE quiz_id = ? AND outcome IS NOT NULL
            GROUP BY outcome
        ''', (quiz_id,))
        outcomes = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Calculate percentages
        outcome_percentages = {}
        if total > 0 and outcomes:
            for outcome, count in outcomes.items():
                outcome_percentages[outcome] = round((count / total) * 100, 1)
        
        # Average score (for trivia quizzes)
        cursor.execute('''
            SELECT AVG(score)
            FROM responses
            WHERE quiz_id = ? AND score IS NOT NULL
        ''', (quiz_id,))
        avg_score = cursor.fetchone()[0]
        
        # Score distribution
        cursor.execute('''
            SELECT score, COUNT(*) as count
            FROM responses
            WHERE quiz_id = ? AND score IS NOT NULL
            GROUP BY score
            ORDER BY score
        ''', (quiz_id,))
        score_dist = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            "total_responses": total,
            "outcome_distribution": outcomes,
            "outcome_percentages": outcome_percentages,
            "average_score": round(avg_score, 1) if avg_score else None,
            "score_distribution": score_dist
        }

    def get_response(self, response_id: str) -> Optional[dict]:
        """Get a specific response by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, quiz_id, user_name, answers, outcome, score, created_at
            FROM responses WHERE id = ?
        ''', (response_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "quiz_id": row[1],
                "user_name": row[2],
                "answers": json.loads(row[3]),
                "outcome": row[4],
                "score": row[5],
                "created_at": row[6]
            }
        return None

    def register_quiz(self, quiz_id: str, quiz_type: str, category: str, title: str):
        """Register a quiz in the database for tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO quizzes (id, type, category, title, created_at, play_count)
            VALUES (?, ?, ?, ?, ?, COALESCE(
                (SELECT play_count FROM quizzes WHERE id = ?), 0
            ))
        ''', (quiz_id, quiz_type, category, title, datetime.now().isoformat(), quiz_id))
        
        conn.commit()
        conn.close()

    def get_all_quizzes(self) -> list:
        """Get all registered quizzes with their stats."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, type, category, title, created_at, play_count
            FROM quizzes
            ORDER BY created_at DESC
        ''')
        
        quizzes = []
        for row in cursor.fetchall():
            quizzes.append({
                "id": row[0],
                "type": row[1],
                "category": row[2],
                "title": row[3],
                "created_at": row[4],
                "play_count": row[5]
            })
        
        conn.close()
        return quizzes

    def get_recent_responses(self, quiz_id: str, limit: int = 10) -> list:
        """Get recent responses for a quiz."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_name, outcome, score, created_at
            FROM responses
            WHERE quiz_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (quiz_id, limit))
        
        responses = []
        for row in cursor.fetchall():
            responses.append({
                "id": row[0],
                "user_name": row[1],
                "outcome": row[2],
                "score": row[3],
                "created_at": row[4]
            })
        
        conn.close()
        return responses


def main():
    """Test the database module."""
    db = Database("data/test_responses.db")
    
    print("=" * 50)
    print("Testing Database Module")
    print("=" * 50)
    
    # Register a test quiz
    print("\n[Registering Quiz]")
    db.register_quiz("test-personality-quiz", "personality", "movies", "Which Movie Hero Are You?")
    print("Quiz registered!")
    
    # Save some test responses
    print("\n[Saving Responses]")
    r1 = db.save_response("test-personality-quiz", "Alice", ["a", "b", "a", "c"], outcome="hero")
    r2 = db.save_response("test-personality-quiz", "Bob", ["b", "b", "c", "a"], outcome="villain")
    r3 = db.save_response("test-personality-quiz", "Charlie", ["a", "a", "a", "a"], outcome="hero")
    print(f"Saved responses: {r1}, {r2}, {r3}")
    
    # Get stats
    print("\n[Quiz Stats]")
    stats = db.get_quiz_stats("test-personality-quiz")
    print(f"Total responses: {stats['total_responses']}")
    print(f"Outcome distribution: {stats['outcome_distribution']}")
    print(f"Outcome percentages: {stats['outcome_percentages']}")
    
    # Get all quizzes
    print("\n[All Quizzes]")
    quizzes = db.get_all_quizzes()
    for q in quizzes:
        print(f"  - {q['title']} (played {q['play_count']} times)")
    
    # Cleanup test db
    import os
    os.remove("data/test_responses.db")
    print("\nTest database cleaned up.")


if __name__ == "__main__":
    main()
