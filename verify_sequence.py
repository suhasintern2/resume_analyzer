#!/usr/bin/env python3
"""
Verification script for MCQ answer sequence.
This independently loads the JSON dataset and verifies what the daily set should be.
"""

import json
import os
from datetime import date

def load_mcq_dataset(dataset_path):
    """Load and validate the MCQ dataset from JSON file."""
    if not os.path.isfile(dataset_path):
        raise FileNotFoundError(f"MCQ dataset not found at {dataset_path}")

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
            raise ValueError(
                "MCQ dataset must contain either a 'sections' object with 6 section keys "
                "or a 'columns' array with exactly 6 elements."
            )

    return {"sections": sections_data}

def generate_daily_set_sequential(sections_data, business_date=None):
    """
    Generate daily MCQ set using simple sequential selection:
    - Take the first DAILY_DRAW_COUNTS[i] questions from each section in order
    """
    if business_date is None:
        business_date = date(2026, 9, 25)  # From the logs

    MCQ_SECTIONS = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
    DAILY_DRAW_COUNTS = [1, 1, 3, 1, 2, 2]  # Matches section order above
    QUESTIONS_PER_DAY = sum(DAILY_DRAW_COUNTS)  # 10

    # Validate we have all sections
    missing_sections = [s for s in MCQ_SECTIONS if s not in sections_data]
    if missing_sections:
        raise ValueError(f"Missing sections in MCQ dataset: {missing_sections}")

    # Validate question counts per section
    expected_counts = {
        "ENGLISH": 10,
        "APTITUDE": 10,
        "MERN": 30,
        "PYTHON": 10,
        "DBMS": 20,
        "BACKEND_MID": 20,
    }

    for section_name, questions in sections_data.items():
        if section_name in expected_counts:
            expected_count = expected_counts[section_name]
            if len(questions) != expected_count:
                raise ValueError(
                    f"Section {section_name} has {len(questions)} questions, "
                    f"expected {expected_count}"
                )

    # Generate questions using simple sequential selection
    selected_questions = []  # Will contain tuples of (section_name, question_dict)
    answer_key_chars = []

    for section_idx, (section_name, draw_count) in enumerate(zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS)):
        questions = sections_data[section_name]
        if not questions:
            continue

        # Simple sequential: take first 'draw_count' questions
        for i in range(min(draw_count, len(questions))):
            question_data = questions[i]
            selected_questions.append((section_name, question_data))
            answer_key_chars.append(question_data["correct_option"])

    answer_key_sequence = "".join(answer_key_chars)
    return answer_key_sequence

def main():
    """Main verification function."""
    print("MCQ Answer Sequence Verification")
    print("=" * 40)

    # Load the dataset
    dataset_path = "generated/mcq_bank/mcq_dataset.json"
    print(f"Loading dataset from: {dataset_path}")

    try:
        dataset = load_mcq_dataset(dataset_path)
        sections_data = dataset["sections"]
        print("Dataset loaded successfully!")

        # Show section counts
        for section in ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]:
            count = len(sections_data[section])
            print(f"  {section}: {count} questions")

    except Exception as e:
        print(f"Error loading dataset: {e}")
        return 1

    # Generate the daily set using sequential approach
    try:
        sequence = generate_daily_set_sequential(sections_data)
        print(f"\nGenerated answer key sequence (sequential): {sequence}")
    except Exception as e:
        print(f"Error generating daily set: {e}")
        return 1

    # User's expected answer key from their message:
    # 1.b) neither of the students has submitted his assignment. → B (ENGLISH[0])
    # 2.b) 250 → B (APTITUDE[0])
    # 3.b) document-oriented nosql → B (MERN[0])
    # 4.b) a table → B (MERN[1]: collection equivalent to table)
    # 5.b) bson → B (MERN[2]: internal storage format)
    # 6.a) <class 'list'> → A (PYTHON[0]: type([]))
    # 7.a) atomicity, consistency, isolation, durability → A (DBMS[0]: ACID)
    # 8.b) 2nf → B (DBMS[1]: removes partial dependency)
    # 9.a) representational state transfer → A (BACKEND_MID[0]: REST)
    # 10.b) get this is dispay on the the sequenze t from sections format with 6 columns → B (BACKEND_MID[1]: HTTP 401 Unauthorized)
    expected_sequence = "BBBBBAABAB"

    print(f"Expected answer key sequence:      {expected_sequence}")
    print(f"Generated answer key sequence:     {sequence}")

    if sequence == expected_sequence:
        print("\n✓ SUCCESS: Sequences match!")
        return 0
    else:
        print("\n✗ FAILURE: Sequences do not match!")
        print("\nDifferences:")
        for i, (exp, gen) in enumerate(zip(expected_sequence, sequence)):
            if exp != gen:
                print(f"  Position {i+1}: expected '{exp}', got '{gen}'")
        return 1

if __name__ == "__main__":
    exit(main())