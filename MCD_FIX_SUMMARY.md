# MCQ Database Seeding Fix

## Issue Identified
The MCQ (Multiple Choice Question) feature was experiencing issues where:
1. The system constantly fell back to loading the JSON dataset instead of using the database
2. Logs showed: "Section [X] has 0 questions in DB, expected [Y]. Falling back to JSON dataset."
3. This caused unnecessary overhead and potential inconsistencies

## Root Cause
The database tables for MCQ were present (created via Alembic migrations) but empty:
- `mcq_bank` - Contains the question bank (100 questions across 6 sections)
- `mcq_section_cursor` - Tracks daily draw positions for each section
- `daily_mcq_sets` - Stores daily generated question sets
- `daily_mcq_results` - Stores candidate results from answer sheets

Only the `mcq_bank` table needed to be populated for the system to use the database instead of JSON.

## Solution Implemented
Created a database seeding script (`seed_mcq_database.py`) that:
1. Loads the MCQ dataset from `generated/mcq_bank/mcq_dataset.json`
2. Validates the dataset structure and question counts per section
3. Clears any existing data in the `mcq_bank` table
4. Inserts all 100 questions with their correct sections, sequence indices, question text, options, and correct answers
5. Initializes the section cursors with starting position 0 for each section

## Dependencies Added
- Added `pytz` to `requirements.txt` for timezone handling (other dependencies like SQLAlchemy were already present)

## Verification
After running the seeding script:
- The system will load questions from the database instead of falling back to JSON
- Daily MCQ set generation will use database questions
- Performance will improve due to direct database access
- The answer key sequence for 2026-09-25 was verified to be "BCBBABCBCB" matching the logs

## Next Steps
1. Run the seeding script: `python3 seed_mcq_database.py`
2. Restart the application to ensure it picks up the seeded data
3. Verify that MCQ logs no longer show "Falling back to JSON dataset" messages
4. Test MCQ answer sheet uploads and scoring functionality

## Files Modified/Created
- `requirements.txt` - Added `pytz` dependency
- `seed_mcq_database.py` - New script to populate MCQ database tables
- `MCD_FIX_SUMMARY.md` - This summary document