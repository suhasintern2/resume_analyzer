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
 * Returns InterviewDetail.
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
 * Select a candidate for next step.
 * POST /api/interviews/{id}/select-next-round
 */
export async function selectNextRound(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/select-next-round`,
    { method: 'POST' },
  );
  return _json(response);
}

/**
 * Delete an interview and all its associated files.
 * DELETE /api/interviews/{id}
 */
export async function deleteInterview(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}`,
    { method: 'DELETE' },
  );
  return _json(response);
}

// ── Dashboard — Mark as Done ────────────────────────────────────────

/**
 * Mark an interview as done. Auto-deletes generated PDFs.
 * Returns { success, interview_id, status, message }
 */
export async function markAsDone(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/mark-as-done`,
    { method: 'POST' },
  );
  return _json(response);
}

// ── Dashboard — PDF Downloads ───────────────────────────────────────

/**
 * Download a PDF for an interview (interviewer or hr role).
 * Returns a Blob.
 */
export async function downloadInterviewPDF(interviewId, role) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/pdf/${encodeURIComponent(role)}`,
  );
  if (!response.ok) {
    throw new Error(`PDF download failed (${response.status})`);
  }
  return response.blob();
}

// ── Dashboard — Documents ─────────────────────────────────────────────────────

/**
 * List generated documents for an interview.
 * Returns { interview_id, documents: [{ file_type, file_path, created_at }] }
 */
export async function listDocuments(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/documents`,
  );
  return _json(response);
}

/**
 * Download a generated document (question_sheet | answer_key) as a Blob.
 */
export async function downloadInterviewDocument(
  interviewId,
  fileType,
) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/documents/${encodeURIComponent(fileType)}`,
  );
  return _blob(response);
}

/**
 * Download a role-specific DOCX (interviewer | hr | candidate) as a Blob.
 * Generated on-the-fly from evaluation keys.
 */
export async function downloadRoleDocx(
  interviewId,
  role,
) {
  const params = new URLSearchParams({
    role,
  });
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/documents/question_sheet?${params}`,
  );
  return _blob(response);
}

// ── Dashboard — Answer Script Upload & Segmentation ──────────────────────────

/**
 * Upload one or more answer-script pages for an interview.
 * files: FileList or File[]
 * Returns AnswerScriptUploadResponse
 */
export async function uploadAnswerScript(
  interviewId,
  files,
) {
  const formData = new FormData();
  const fileArray = Array.from(files);
  fileArray.forEach((f) => formData.append('files', f));

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
 * Get segmented answer blocks for a SEGMENTED or SEGMENTATION_UNCERTAIN interview.
 * Returns { interview_id, status, matched, segments: AnswerSegmentOut[] }
 */
export async function getSegments(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/segments`,
  );
  return _json(response);
}

/**
 * Reassign a segment to a different question number (manual correction).
 * Returns { interview_id, status, matched, segment }
 */
export async function reassignSegment(
  interviewId,
  segmentId,
  questionNumber,
) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/segments/${segmentId}/reassign`,
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
 * Trigger deterministic evaluation for a SEGMENTED interview.
 * Returns EvaluationStartResponse { success, interview_id, status }
 */
export async function startEvaluation(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/evaluate`,
    { method: 'POST' },
  );
  return _json(response);
}

/**
 * Retrieve the current evaluation result.
 * Returns EvaluationDetailOut
 */
export async function getEvaluation(interviewId) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/evaluation`,
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
) {
  const response = await fetch(
    `/api/interviews/${encodeURIComponent(interviewId)}/evaluation/questions/${questionNumber}/override`,
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

// ─────────────────────────────────────────────────────────────────────────
// MCQ Question Bank (Task 13)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Get available MCQ days (1-10).
 * Returns { days: number[] }
 */
export async function getMCQDays() {
  const response = await fetch('/api/mcq/days');
  return _json(response);
}

/**
 * Get status for a specific day.
 * Returns { day, available, questions, question_count, correct_answers_available }
 */
export async function getMCQDay(day) {
  const response = await fetch(`/api/mcq/day/${day}`);
  return _json(response);
}

/**
 * Download MCQ question paper DOCX for a specific day.
 * Returns a Blob.
 */
export async function downloadMCQPaper(day) {
  const response = await fetch(`/api/mcq/day/${day}/download`);
  if (!response.ok) {
    throw new Error(`Failed to download question paper (${response.status})`);
  }
  return response.blob();
}

/**
 * Upload completed MCQ answer sheets for a specific day.
 * files: FileList or File[] (text files with candidate answers)
 * Returns { success, day, scores, message }
 */
export async function uploadMCQAnswers(day, files) {
  const formData = new FormData();
  const fileArray = Array.from(files);
  fileArray.forEach((f) => formData.append('files', f));

  const response = await fetch(
    `/api/mcq/day/${day}/upload`,
    { method: 'POST', body: formData },
  );
  return _json(response);
}

/**
 * Get the correct answer key for a specific day.
 * Returns { day, questions, correct_answers, total_questions }
 */
export async function getMCQResults(day) {
  const response = await fetch(`/api/mcq/day/${day}/results`);
  return _json(response);
}

/**
 * Download MCQ answer key DOCX for a specific day.
 * Returns a Blob.
 */
export async function downloadMCQAnswerKey(day) {
  const response = await fetch(`/api/mcq/day/${day}/download-answer-key`);
  if (!response.ok) {
    throw new Error(`Failed to download answer key (${response.status})`);
  }
  return response.blob();
}
