// ─────────────────────────────────────────────────────────────────────────────
// api.js — All backend API calls for the Resume Analyzer & Interview Dashboard
// ─────────────────────────────────────────────────────────────────────────────

// ── Helpers ──────────────────────────────────────────────────────────────────

async function _json(response) {
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Server returned non-JSON response (${response.status})`);
  }
  if (!response.ok) {
    throw new Error(data.detail || data.error || `Request failed (${response.status})`);
  }
  return data;
}

async function _blob(response) {
  if (!response.ok) {
    let msg = `Download failed (${response.status})`;
    try {
      const data = await response.json();
      msg = data.detail || data.error || msg;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return response.blob();
}

// ── Legacy MVP endpoints (kept intact) ───────────────────────────────────────

export async function generateInterviewQA(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/generate', {
    method: 'POST',
    body: formData,
  });

  const data = await _json(response);

  if (!data.success || !data.result) {
    throw new Error(data.error || 'Failed to generate interview questions.');
  }
  return data.result;
}

export async function downloadDocx(result, role) {
  const response = await fetch(`/api/download/docx?role=${encodeURIComponent(role)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result),
  });
  return _blob(response);
}

// ── Dashboard — Interview Management ─────────────────────────────────────────

/**
 * List all interviews ordered by creation date descending.
 * Returns { interviews: InterviewListItem[] }
 * Each item now carries a `rounds` array (status + percentage per round).
 */
export async function listInterviews() {
  const response = await fetch('/api/interviews');
  return _json(response);
}

/**
 * Create a new interview from a resume file.
 * Returns { success, interview_id, status }
 */
export async function createInterview(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/interviews', {
    method: 'POST',
    body: formData,
  });
  return _json(response);
}

/**
 * Get a single interview by its display ID (e.g. "INT-20260914-001").
 * Returns InterviewDetail — includes `rounds` array.
 */
export async function getInterview(interviewId) {
  const response = await fetch(`/api/interviews/${encodeURIComponent(interviewId)}`);
  return _json(response);
}

/**
 * Rename an interview's dashboard label.
 */
export async function renameInterview(interviewId, displayName) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/display-name`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: displayName || null }),
    },
  );
  return _json(response);
}

/**
 * Select a candidate for Round 2 (flips access gate on round 1).
 * POST /api/interviews/{id}/select-next-round
 */
export async function selectNextRound(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/select-next-round`,
    { method: 'POST' },
  );
  return _json(response);
}

// ── Dashboard — Documents ─────────────────────────────────────────────────────

/**
 * List generated documents for an interview.
 * Returns { interview_id, documents: [{ file_type, file_path, round_number, created_at }] }
 */
export async function listDocuments(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/documents`,
  );
  return _json(response);
}

/**
 * Download a generated document (question_sheet | answer_key) as a Blob.
 * roundNumber selects which round's document to download; defaults to 1.
 */
export async function downloadInterviewDocument(
  interviewId,
  fileType,
  roundNumber = 1,
) {
  const params = new URLSearchParams({ round_number: String(roundNumber) });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/documents/${encodeURIComponent(fileType)}?${params}`,
  );
  return _blob(response);
}

// ── Dashboard — Answer Script Upload & Segmentation ──────────────────────────

/**
 * Upload one or more answer-script pages for an interview.
 * files: FileList or File[] — roundNumber defaults to 1.
 * Returns AnswerScriptUploadResponse
 */
export async function uploadAnswerScript(
  interviewId,
  files,
  roundNumber = 1,
) {
  const formData = new FormData();
  const fileArray = Array.from(files);
  fileArray.forEach((f) => formData.append('files', f));
  formData.append('round_number', String(roundNumber));

  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/answer-script`,
    {
      method: 'POST',
      body: formData,
    },
  );
  return _json(response);
}

/**
 * Get segmented answer blocks for a SEGMENTED or SEGMENTATION_UNCERTAIN round.
 * Returns { interview_id, round_number, status, matched, segments: AnswerSegmentOut[] }
 */
export async function getSegments(interviewId, roundNumber = 1) {
  const params = new URLSearchParams({ round_number: String(roundNumber) });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/segments?${params}`,
  );
  return _json(response);
}

/**
 * Reassign a segment to a different question number (manual correction).
 * Returns { interview_id, round_number, status, matched, segment }
 */
export async function reassignSegment(
  interviewId,
  segmentId,
  questionNumber,
  roundNumber = 1,
) {
  const params = new URLSearchParams({ round_number: String(roundNumber) });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/segments/${segmentId}/reassign?${params}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_number: questionNumber }),
    },
  );
  return _json(response);
}

// ── Dashboard — Evaluation ────────────────────────────────────────────────────

/**
 * Trigger deterministic evaluation for a SEGMENTED round.
 * Returns EvaluationStartResponse { success, interview_id, status }
 */
export async function startEvaluation(interviewId, roundNumber = 1) {
  const params = new URLSearchParams({ round_number: String(roundNumber) });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/evaluate?${params}`,
    { method: 'POST' },
  );
  return _json(response);
}

/**
 * Retrieve the current evaluation result for a round.
 * Returns EvaluationDetailOut
 */
export async function getEvaluation(interviewId, roundNumber = 1) {
  const params = new URLSearchParams({ round_number: String(roundNumber) });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/evaluation?${params}`,
  );
  return _json(response);
}

/**
 * Override a question score with a required reason.
 * Returns { success, interview_id, question_number, original_score, override_score, ... }
 */
export async function overrideScore(
  interviewId,
  questionNumber,
  overrideScore,
  overrideReason,
  roundNumber = 1,
) {
  const params = new URLSearchParams({ round_number: String(roundNumber) });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/evaluation/questions/${questionNumber}/override?${params}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        override_score: overrideScore,
        override_reason: overrideReason,
      }),
    },
  );
  return _json(response);
}
