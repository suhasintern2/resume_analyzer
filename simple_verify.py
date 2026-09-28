#!/usr/bin/env python3
"""
Simple verification of MCQ sequence generation algorithms.
"""

import json
import os
from datetime import date

def load_sections_from_json(dataset_path):
    """Load sections from MCQ dataset JSON."""
    with open(dataset_path) as f:
        data = json.load(f)

    sections_data = data.get("sections", {})
    if not sections_data:
        # Handle old format
        columns = data.get("columns", [])
        if columns and len(columns) == 6:
            section_names = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
            sections_data = {name: columns[i] for i, name in enumerate(section_names) if i < len(columns)}

    return sections_data

def generate_rotation_sequence(sections_data, business_date=None):
    """Generate sequence using current rotation-based algorithm."""
    if business_date is None:
        business_date = date(2026, 9, 25)  # From logs

    MCQ_SECTIONS = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
    DAILY_DRAW_COUNTS = [1, 1, 3, 1, 2, 2]

    # Calculate day offset (days since 1970-01-01)
    day_offset = (business_date - date(1970, 1, 1)).days

    answer_key = []
    for section_name, draw_count in zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS):
        questions = sections_data[section_name]
        section_length = len(questions)
        start_idx = (day_offset * draw_count) % section_length

        for i in range(draw_count):
            idx = (start_idx + i) % section_length
            answer_key.append(questions[idx]["correct_option"])

    return "".join(answer_key)

def generate_sequential_sequence(sections_data):
    """Generate sequence using simple sequential approach."""
    MCQ_SECTIONS = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
    DAILY_DRAW_COUNTS = [1, 1, 3, 1, 2, 2]

    answer_key = []
    for section_name, draw_count in zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS):
        questions = sections_data[section_name]
        # Take first 'draw_count' questions
        for i in range(min(draw_count, len(questions))):
            answer_key.append(questions[i]["correct_option"])

    return "".join(answer_key)

def main():
    print("MCQ Sequence Algorithm Comparison")
    print("=" * 40)

    # Load dataset
    dataset_path = "generated/mcq_bank/mcq_dataset.json"
    if not os.path.isfile(dataset_path):
        print(f"ERROR: Dataset not found at {dataset_path}")
        return 1

    sections_data = load_sections_from_json(dataset_path)
    print(f"Loaded dataset with {len(sections_data)} sections")

    # Generate sequences
    rotation_seq = generate_rotation_sequence(sections_data)
    sequential_seq = generate_sequential_sequence(sections_data)

    # User's expected sequence from their answer key
    expected_seq = "BBBBBAABAB"

    print(f"\nRotation-based (current):   {rotation_seq}")
    print(f"Sequential (proposed):      {sequential_seq}")
    print(f"User's expected:            {expected_seq}")

    print(f"\nMatches expected?")
    print(f"  Rotation:  {rotation_seq == expected_seq}")
    print(f"  Sequential: {sequential_seq == expected_seq}")

    if rotation_seq != expected_seq:
        print(f"\nRotation differences:")
        for i, (r, e) in enumerate(zip(rotation_seq, expected_seq)):
            if r != e:
                print(f"  Pos {i+1}: rotation={r}, expected={e}")

    if sequential_seq != expected_seq:
        print(f"\nSequential differences:")
        for i, (s, e) in enumerate(zip(sequential_seq, expected_seq)):
            if s != e:
                print(f"  Pos {i+1}: sequential={s}, expected={e}")

    # Return success if sequential matches expected
    return 0 if sequential_seq == expected_seq else 1

if __name__ == "__main__":
    exit(main())