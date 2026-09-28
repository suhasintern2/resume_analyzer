#!/usr/bin/env python3
"""
Seed the MCQ database tables with questions from the JSON dataset.
This script populates the mcq_bank table so the system uses the database
instead of falling back to JSON.
"""

import json
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the app directory to the path so we can import models
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.db.models import McqBank, Base
from app.db import DATABASE_URL
from app.config import settings

def seed_mcq_database():
    """Seed the mcq_bank table with questions from the JSON dataset."""

    # Load the MCQ dataset
    dataset_path = settings.MCQ_DATASET_PATH
    if not os.path.isfile(dataset_path):
        print(f"ERROR: MCQ dataset not found at {dataset_path}")
        return False

    print(f"Loading MCQ dataset from {dataset_path}")
    with open(dataset_path) as f:
        data = json.load(f)

    # Handle both old format (columns) and new format (sections)
    sections_data = data.get("sections", {})
    if not sections_data:
        # Try to load from columns format (old)
        columns = data.get("columns", [])
        if columns and len(columns) == 6:
            # Convert columns to sections
            section_names = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
            sections_data = {}
            for i, section_name in enumerate(section_names):
                if i < len(columns):
                    sections_data[section_name] = columns[i]
                else:
                    sections_data[section_name] = []
        else:
            print("ERROR: MCQ dataset must contain either a 'sections' object with 6 section keys "
                  "or a 'columns' array with exactly 6 elements.")
            return False

    # Validate we have all required sections
    required_sections = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
    missing_sections = [s for s in required_sections if s not in sections_data]
    if missing_sections:
        print(f"ERROR: Missing sections in MCQ dataset: {missing_sections}")
        return False

    # Expected counts per section
    expected_counts = {
        "ENGLISH": 10,
        "APTITUDE": 10,
        "MERN": 30,
        "PYTHON": 10,
        "DBMS": 20,
        "BACKEND_MID": 20,
    }

    # Validate each section
    for section_name, questions in sections_data.items():
        if section_name not in required_sections:
            print(f"WARNING: Unexpected section in MCQ dataset: {section_name}")
            continue

        expected_count = expected_counts[section_name]
        if len(questions) != expected_count:
            print(f"ERROR: Section {section_name} has {len(questions)} questions, "
                  f"expected {expected_count}")
            return False

    # Connect to the database
    print(f"Connecting to database: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        # Clear existing data (if any)
        print("Clearing existing MCQ bank data...")
        session.query(McqBank).delete()
        session.commit()

        # Insert questions for each section
        total_questions = 0
        for section_name, questions in sections_data.items():
            print(f"Inserting {len(questions)} questions for section '{section_name}'...")

            for q in questions:
                mcq_question = McqBank(
                    section=section_name,
                    sequence_index=q["sequence_index"],
                    question_text=q["question_text"],
                    options=q["options"],
                    correct_option=q["correct_option"]
                )
                session.add(mcq_question)
                total_questions += 1

            # Commit after each section to avoid large transactions
            session.commit()

        print(f"Successfully inserted {total_questions} questions into the MCQ bank.")

        # Also initialize the section cursors if they don't exist
        from app.db.models import McqSectionCursor
        print("Initializing section cursors...")
        for section_name in required_sections:
            existing_cursor = session.query(McqSectionCursor).filter_by(section=section_name).first()
            if not existing_cursor:
                cursor = McqSectionCursor(section=section_name, next_index=0)
                session.add(cursor)
        session.commit()
        print("Section cursors initialized.")

        return True

    except Exception as e:
        print(f"ERROR: Failed to seed MCQ database: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    print("Seeding MCQ database...")
    if seed_mcq_database():
        print("\nSUCCESS: MCQ database seeded successfully!")
        print("The system will now use the database instead of falling back to JSON.")
    else:
        print("\nFAILED: Could not seed MCQ database.")
        sys.exit(1)