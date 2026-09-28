#!/usr/bin/env python3
"""
Verify the business date calculation for MCQ daily sets.
"""

from datetime import date, datetime, timezone
import pytz

def get_business_date_custom(business_tz_str="Europe/London"):
    """Replicate the business date calculation from mcq_service.py."""
    utc_now = datetime.now(timezone.utc)
    business_tz = pytz.timezone(business_tz_str)
    business_time = utc_now.astimezone(business_tz)
    return business_time.date()

def main():
    print("Business Date Verification")
    print("=" * 30)

    # Current UTC time (we'll use a fixed time for reproducibility)
    # From the logs: "2026-09-25 08:31:55,255" appears to be a timestamp
    log_time_str = "2026-09-25 08:31:55.255000"
    utc_now = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
    print(f"UTC time from logs: {utc_now}")

    # Calculate business date
    business_date = get_business_date_custom()
    print(f"Business date (Europe/London): {business_date}")

    # Calculate day offset for MCQ daily set generation
    epoch = date(1970, 1, 1)
    day_offset = (business_date - epoch).days
    print(f"Day offset (days since 1970-01-01): {day_offset}")

    # What day number is this for MCQ purposes?
    # The formula in _generate_daily_mcq_set uses: start_idx = (day_offset * draw_count) % section_length
    # Where day_offset = (business_date - datetime(1970, 1, 1).date()).days

    print(f"\nFor date {business_date}:")
    print(f"  Day offset: {day_offset}")

    # Check if this should be considered "day 1" for MCQ
    # If the MCQ cycle starts on a specific date, we might need to adjust
    # But the current code doesn't do any such adjustment - it uses the raw offset

    # Let's see what date would give day_offset = 0 (which would be day 1 in their 1-indexed system if they subtracted 1)
    # Actually, looking at the code:
    #   day_offset = (business_date - datetime(1970, 1, 1).date()).days
    #   start_idx = (day_offset * draw_count) % section_length
    #
    # There's no "- 1" adjustment in the actual code - I misread it earlier.
    # The comment says "((day-1) * draw_count)" but the code uses day_offset directly.
    #
    # So for business_date = 1970-01-01, day_offset = 0
    # For business_date = 1970-01-02, day_offset = 1
    # etc.

    # The logs show they got a sequence for 2026-09-25, so let's verify what sequence
    # that date should produce with the CURRENT (rotation-based) algorithm

    print(f"\n--- Current Algorithm (Rotation-Based) ---")
    from datetime import date
    sections_data = {
        "ENGLISH": [{"correct_option": c} for c in "BBBBBBBBBB"],  # Simplified for demo
        "APTITUDE": [{"correct_option": c} for c in "BBBBBBBBBB"],
        "MERN": [{"correct_option": c} for c in "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"],  # 30 B's for simplicity
        "PYTHON": [{"correct_option": c} for c in "BBBBBBBBBB"],
        "DBMS": [{"correct_option": c} for c in "BBBBBBBBBBBBBBBBBBBB"],  # 20 B's
        "BACKEND_MID": [{"correct_option": c} for c in "BBBBBBBBBBBBBBBBBBBB"],  # 20 B's
    }

    # Actually, let's use the real data from JSON
    import json
    with open('generated/mcq_bank/mcq_dataset.json') as f:
        data = json.load(f)
    sections_data = data["sections"]

    MCQ_SECTIONS = ["ENGLISH", "APTITUDE", "MERN", "PYTHON", "DBMS", "BACKEND_MID"]
    DAILY_DRAW_COUNTS = [1, 1, 3, 1, 2, 2]

    day_offset = (business_date - date(1970, 1, 1)).days
    print(f"Day offset: {day_offset}")

    answer_key = []
    for section_name, draw_count in zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS):
        questions = sections_data[section_name]
        section_length = len(questions)
        start_idx = (day_offset * draw_count) % section_length
        print(f"  {section_name}: length={section_length}, draw={draw_count}, start_idx={start_idx}")
        for i in range(draw_count):
            idx = (start_idx + i) % section_length
            answer_key.append(questions[idx]["correct_option"])

    rotation_sequence = "".join(answer_key)
    print(f"  Generated sequence (rotation): {rotation_sequence}")

    # Now check what the sequential approach would give
    print(f"\n--- Proposed Algorithm (Sequential) ---")
    answer_key_seq = []
    for section_name, draw_count in zip(MCQ_SECTIONS, DAILY_DRAW_COUNTS):
        questions = sections_data[section_name]
        # Take first 'draw_count' questions
        for i in range(min(draw_count, len(questions))):
            answer_key_seq.append(questions[i]["correct_option"])

    sequential_sequence = "".join(answer_key_seq)
    print(f"  Generated sequence (sequential): {sequential_sequence}")

    # User's expected sequence
    expected = "BBBBBAABAB"
    print(f"\nUser's expected sequence:        {expected}")
    print(f"Matches rotation?  {rotation_sequence == expected}")
    print(f"Matches sequential? {sequential_sequence == expected}")

if __name__ == "__main__":
    main()