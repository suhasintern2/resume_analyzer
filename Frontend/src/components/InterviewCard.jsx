/**
 * InterviewCard — one card per interview in the dashboard (Task 12 revision).
 * Shows: ID, candidate name, per-round status / documents / uploads, and
 * evaluation summaries per round.
 *
 * Round 2 is always present but gated: uploads / evaluation / downloads for
 * round 2 are locked until round 1 is EVALUATED and the staff member
 * selected the candidate for the next round.
 */
import { useState } from 'react';
import ProcessingStages from './ProcessingStages';
import DocumentActions from './DocumentActions';
import AnswerScriptUpload from './AnswerScriptUpload';
import SegmentationCorrectionView from './SegmentationCorrectionView';
import EvaluationSummary from './EvaluationSummary';
import { startEvaluation, selectNextRound } from '../services/api';

const STATUS_CLASSES = {
  QUEUED:                 'status-badge--queued',
  PROCESSING:             'status-badge--processing',
  COMPLETED:              'status-badge--completed',
  FAILED:                 'status-badge--failed',
  ANSWER_UPLOADED:        'status-badge--answer',
  SEGMENTED:              'status-badge--answer',
  SEGMENTATION_UNCERTAIN: 'status-badge--warning',
  EVALUATING:             'status-badge--evaluating',
  EVALUATED:              'status-badge--evaluated',
  EVALUATION_FAILED:      'status-badge--failed',
  QUESTIONS_READY:        'status-badge--completed',
  QUESTIONS_GENERATING:   'status-badge--processing',
  NOT_STARTED:            'status-badge--queued',
};

const STATUS_LABELS = {
  QUEUED:                 'Queued',
  PROCESSING:             'Processing',
  COMPLETED:              'Completed',
  FAILED:                 'Failed',
  ANSWER_UPLOADED:        'Answer Uploaded',
  SEGMENTED:              'Segmented',
  SEGMENTATION_UNCERTAIN: 'Segmentation Uncertain',
  EVALUATING:             'Evaluating',
  EVALUATED:              'Evaluated',
  EVALUATION_FAILED:      'Evaluation Failed',
  QUESTIONS_READY:        'Questions Ready',
  QUESTIONS_GENERATING:   'Generating…',
  NOT_STARTED:            'Not started',
};

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'EVALUATED', 'EVALUATION_FAILED']);

/**
 * Derive whether round 2 is locked for this interview.
 * Locked when: round 1 is missing, not evaluated, or not selected_for_next_round.
 */
function round2Locked(rounds) {
  if (!Array.isArray(rounds) || rounds.length < 2) return true;
  const r1 = rounds.find((r) => r.round_number === 1);
  if (!r1) return true;
  if (r1.status !== 'EVALUATED') return true;
  return r1.selected_for_next_round !== true;
}

function roundByNumber(rounds, num) {
  if (!Array.isArray(rounds)) return null;
  return rounds.find((r) => r.round_number === num) || null;
}

export default function InterviewCard({
  interview,
  documents = [],
  onToast,
  onRefresh,
}) {
  const [evaluating, setEvaluating]  = useState(false);
  const [selectingR2, setSelectingR2] = useState(false);
  const [showContact, setShowContact] = useState(false);
  // Track which round's eval detail is toggled open
  const [showRoundDetail, setShowRoundDetail] = useState({});

  const {
    interview_id, candidate_name, status, processing_stage, error_reason,
    created_at, email, phone,
    rounds = [],
  } = interview;

  const r1 = roundByNumber(rounds, 1);
  const r2 = roundByNumber(rounds, 2);
  const isR2Locked = round2Locked(rounds);

  const statusLabel = STATUS_LABELS[status] || status;
  const statusCls   = STATUS_CLASSES[status] || '';
  const isTerminal  = TERMINAL.has(status);
  const hasContact  = Boolean(email || phone);

  const createdDate = created_at
    ? new Date(created_at).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
    : '';

  async function handleEvaluate(roundNumber) {
    setEvaluating(true);
    try {
      await startEvaluation(interview_id, roundNumber);
      onToast?.(`Evaluation started for Round ${roundNumber}.`);
      onRefresh?.();
    } catch (err) {
      onToast?.(`Could not start evaluation: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  }

  async function handleSelectRound2() {
    setSelectingR2(true);
    try {
      await selectNextRound(interview_id);
      onToast?.('Candidate selected for Round 2 — access unlocked.');
      onRefresh?.();
    } catch (err) {
      onToast?.(`Could not select for Round 2: ${err.message}`);
    } finally {
      setSelectingR2(false);
    }
  }

  function toggleRoundDetail(num) {
    setShowRoundDetail((prev) => ({ ...prev, [num]: !prev[num] }));
  }

  // Group documents by round
  const docsByRound = { 1: [], 2: [] };
  documents.forEach((d) => {
    const rn = d.round_number == null ? 1 : d.round_number;
    if (docsByRound[rn]) docsByRound[rn].push(d);
    else docsByRound[1].push(d);
  });

  return (
    <div className={`interview-card${isTerminal ? '' : ' interview-card--active'}`}>
      {/* ── Card header ───────────────────────────────────────────────── */}
      <div className="interview-card__header">
        <div className="interview-card__id">
          <span className="interview-card__id-label">{interview_id}</span>
          <span className={`status-badge ${statusCls}`}>{statusLabel}</span>
        </div>
        <div className="interview-card__meta">
          <span className="interview-card__name">
            {candidate_name || <em className="text-muted">Processing…</em>}
          </span>
          {createdDate && (
            <span className="interview-card__date">{createdDate}</span>
          )}
        </div>

        {hasContact && (
          <div className="interview-card__contact">
            <button
              className="btn btn-ghost btn-xs"
              onClick={() => setShowContact((v) => !v)}
            >
              {showContact ? '▲ Hide contact' : '▼ Show contact'}
            </button>
            {showContact && (
              <div className="interview-card__contact-detail">
                {email && <span>✉ {email}</span>}
                {phone && <span>✆ {phone}</span>}
              </div>
            )}
          </div>
        )}

        {/* Top-level headline = Round 1 score when evaluated */}
        {r1?.status === 'EVALUATED' && r1.percentage != null && (
          <div className="interview-card__score-summary">
            <span className="score-pill">
              Round 1: {Number(r1.score ?? 0).toFixed(1)}/{Number(r1.max_score ?? 0).toFixed(0)} &nbsp;·&nbsp; {Number(r1.percentage).toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {error_reason && (
        <div className="interview-card__error">
          <span className="interview-card__error-label">Error:</span> {error_reason}
        </div>
      )}

      <ProcessingStages status={status} processingStage={processing_stage} />

      {/* ── Rounds ────────────────────────────────────────────────────── */}
      <div className="interview-card__rounds">

        {/* ─ Round 1 ─────────────────────────────────────────────────── */}
        <div className="interview-card__round interview-card__round--1">
          <div className="interview-card__round-header">
            <span className="interview-card__round-title">Round 1</span>
            {r1 && (
              <span className={`status-badge badge-sm ${STATUS_CLASSES[r1.status] || ''}`}>
                {STATUS_LABELS[r1.status] || r1.status}
              </span>
            )}
          </div>

          {/* Round 1 documents */}
          {docsByRound[1].length > 0 && (
            <DocumentActions
              interviewId={interview_id}
              documents={docsByRound[1]}
              roundNumber={1}
              onToast={onToast}
            />
          )}

          {/* Round 1 answer script upload */}
          <AnswerScriptUpload
            interviewId={interview_id}
            roundNumber={1}
            status={status}
            onUploaded={onRefresh}
            onToast={onToast}
          />

          {/* Round 1 segmentation correction */}
          {r1 && (r1.status === 'SEGMENTATION_UNCERTAIN' || r1.status === 'SEGMENTED') && status === 'SEGMENTATION_UNCERTAIN' && (
            <SegmentationCorrectionView
              interviewId={interview_id}
              roundNumber={1}
              onCorrected={onRefresh}
              onToast={onToast}
            />
          )}

          {/* Round 1 evaluate button */}
          {(r1?.status === 'SEGMENTED' || (r1?.status === 'SEGMENTATION_UNCERTAIN' && status === 'SEGMENTATION_UNCERTAIN')) && (
            <div className="interview-card__actions">
              <button
                className="btn btn-primary"
                disabled={evaluating}
                onClick={() => handleEvaluate(1)}
              >
                {evaluating ? 'Starting…' : 'Evaluate Round 1'}
              </button>
            </div>
          )}

          {r1?.status === 'EVALUATION_FAILED' && (
            <div className="interview-card__actions">
              <button
                className="btn btn-outline"
                disabled={evaluating}
                onClick={() => handleEvaluate(1)}
              >
                {evaluating ? 'Starting…' : 'Retry Round 1'}
              </button>
            </div>
          )}

          {/* Round 1 evaluation summary */}
          {r1 && (r1.status === 'EVALUATED' || r1.status === 'EVALUATING') && (
            <div className="interview-card__eval-toggle">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => toggleRoundDetail(1)}
              >
                {showRoundDetail[1] ? '▲ Hide Round 1 evaluation' : '▼ View Round 1 evaluation'}
              </button>
              {showRoundDetail[1] && (
                <EvaluationSummary
                  interviewId={interview_id}
                  roundNumber={1}
                  status={r1.status}
                  onToast={onToast}
                />
              )}
            </div>
          )}
        </div>

        {/* ─ Round 2 ─────────────────────────────────────────────────── */}
        <div className={`interview-card__round interview-card__round--2${isR2Locked ? ' interview-card__round--locked' : ''}`}>
          <div className="interview-card__round-header">
            <span className="interview-card__round-title">Round 2</span>
            {r2 && (
              <span className={`status-badge badge-sm ${STATUS_CLASSES[r2.status] || ''}`}>
                {STATUS_LABELS[r2.status] || r2.status}
              </span>
            )}
            {isR2Locked && (
              <span className="interview-card__lock-hint">
                🔒 Complete Round 1 evaluation first
              </span>
            )}
          </div>

          {!isR2Locked && (
            <>
              {/* Round 2 documents */}
              {docsByRound[2].length > 0 && (
                <DocumentActions
                  interviewId={interview_id}
                  documents={docsByRound[2]}
                  roundNumber={2}
                  onToast={onToast}
                />
              )}

              {/* Round 2 answer script upload */}
              <AnswerScriptUpload
                interviewId={interview_id}
                roundNumber={2}
                status={status}
                onUploaded={onRefresh}
                onToast={onToast}
              />

              {/* Round 2 segmentation correction */}
              {r2 && (r2.status === 'SEGMENTATION_UNCERTAIN' || r2.status === 'SEGMENTED') && status === 'SEGMENTATION_UNCERTAIN' && (
                <SegmentationCorrectionView
                  interviewId={interview_id}
                  roundNumber={2}
                  onCorrected={onRefresh}
                  onToast={onToast}
                />
              )}

              {/* Round 2 evaluate button */}
              {r2?.status === 'SEGMENTED' && (
                <div className="interview-card__actions">
                  <button
                    className="btn btn-primary"
                    disabled={evaluating}
                    onClick={() => handleEvaluate(2)}
                  >
                    {evaluating ? 'Starting…' : 'Evaluate Round 2'}
                  </button>
                </div>
              )}

              {r2?.status === 'EVALUATION_FAILED' && (
                <div className="interview-card__actions">
                  <button
                    className="btn btn-outline"
                    disabled={evaluating}
                    onClick={() => handleEvaluate(2)}
                  >
                    {evaluating ? 'Starting…' : 'Retry Round 2'}
                  </button>
                </div>
              )}

              {/* Round 2 evaluation summary */}
              {r2 && (r2.status === 'EVALUATED' || r2.status === 'EVALUATING') && (
                <div className="interview-card__eval-toggle">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => toggleRoundDetail(2)}
                  >
                    {showRoundDetail[2] ? '▲ Hide Round 2 evaluation' : '▼ View Round 2 evaluation'}
                  </button>
                  {showRoundDetail[2] && (
                    <EvaluationSummary
                      interviewId={interview_id}
                      roundNumber={2}
                      status={r2.status}
                      onToast={onToast}
                    />
                  )}
                </div>
              )}

              {/* Round 2 score headline when evaluated */}
              {r2?.status === 'EVALUATED' && r2.percentage != null && (
                <div className="interview-card__score-summary">
                  <span className="score-pill">
                    Round 2: {Number(r2.score ?? 0).toFixed(1)}/{Number(r2.max_score ?? 0).toFixed(0)} &nbsp;·&nbsp; {Number(r2.percentage).toFixed(1)}%
                  </span>
                </div>
              )}
            </>
          )}

          {/* Select-for-Round-2 button — shown when R1 is evaluated but not yet selected */}
          {r1?.status === 'EVALUATED' && r1.selected_for_next_round !== true && (
            <div className="interview-card__actions">
              <button
                className="btn btn-primary"
                disabled={selectingR2}
                onClick={handleSelectRound2}
              >
                {selectingR2 ? 'Selecting…' : 'Select for Round 2'}
              </button>
              <span className="interview-card__lock-hint" style={{ marginLeft: 8 }}>
                Round 2 access is locked until selected
              </span>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
