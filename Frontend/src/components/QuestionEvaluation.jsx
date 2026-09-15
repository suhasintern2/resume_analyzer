/**
 * QuestionEvaluation — per-question evaluation detail:
 * - Score with evidence breakdown (keyword, concept, phrase, similarity, structure)
 * - Status badge (EVALUATED / NO_ANSWER / OCR_FAILED / UNCERTAIN)
 * - Feedback string (deterministic, no LLM)
 * - ScoreOverridePanel (inline, stores original auditably)
 */
import { useState } from 'react';
import ScoreOverridePanel from './ScoreOverridePanel';

const STATUS_LABELS = {
  EVALUATED:    { label: 'Evaluated',     cls: 'badge-success' },
  NO_ANSWER:    { label: 'No Answer',     cls: 'badge-neutral' },
  OCR_FAILED:   { label: 'OCR Failed',    cls: 'badge-error'   },
  UNCERTAIN:    { label: 'Uncertain',     cls: 'badge-warning' },
};

function pct(val) {
  if (val == null) return '—';
  return `${Math.round(val * 100)}%`;
}

function scoreDisplay(score, maxScore) {
  if (score == null) return 'N/A';
  return `${Number(score).toFixed(1)} / ${maxScore ?? 10}`;
}

export default function QuestionEvaluation({
  q,
  interviewId,
  roundNumber = 1,
  onOverrideApplied,
  onToast,
}) {
  const [expanded, setExpanded] = useState(false);
  const [localQ, setLocalQ]     = useState(q);

  const statusMeta = STATUS_LABELS[localQ.status] || { label: localQ.status, cls: 'badge-neutral' };

  function handleOverrideApplied(result) {
    // Update local display without requiring a full page reload
    setLocalQ((prev) => ({
      ...prev,
      override_score: result.override_score,
      override_reason: result.override_reason,
      is_overridden: true,
      // The effective displayed score is the override
      score: result.override_score,
    }));
    onOverrideApplied?.(result);
  }

  const effectiveScore = localQ.is_overridden
    ? localQ.override_score
    : localQ.score;

  return (
    <div className="question-evaluation">
      {/* Header row */}
      <div className="question-evaluation__header">
        <span className="question-evaluation__number">Q{localQ.question_number}</span>

        <span className="question-evaluation__score">
          {scoreDisplay(effectiveScore, localQ.max_score)}
          {localQ.is_overridden && (
            <span className="badge badge-xs badge-overridden" title={`Original: ${localQ.original_score}`}>
              overridden
            </span>
          )}
        </span>

        <span className={`badge badge-xs ${statusMeta.cls}`}>{statusMeta.label}</span>

        <button
          className="btn btn-ghost btn-xs"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? '▲ Hide detail' : '▼ Show detail'}
        </button>
      </div>

      {/* Feedback */}
      {localQ.feedback && (
        <div className="question-evaluation__feedback">{localQ.feedback}</div>
      )}

      {/* Expanded evidence */}
      {expanded && (
        <div className="question-evaluation__detail">
          {localQ.status === 'EVALUATED' && (
            <table className="evidence-table">
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>Coverage</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Keyword coverage</td>
                  <td>{pct(localQ.keyword_score)}</td>
                </tr>
                <tr>
                  <td>Concept coverage</td>
                  <td>{pct(localQ.concept_score)}</td>
                </tr>
                <tr>
                  <td>Phrase matching</td>
                  <td>{pct(localQ.phrase_score)}</td>
                </tr>
                <tr>
                  <td>TF-IDF similarity</td>
                  <td>{pct(localQ.similarity_score)}</td>
                </tr>
                <tr>
                  <td>Structure / type</td>
                  <td>{pct(localQ.structure_score)}</td>
                </tr>
              </tbody>
            </table>
          )}

          {/* Override audit trail */}
          {localQ.is_overridden && (
            <div className="override-audit">
              <span className="override-audit__label">Override reason:</span>
              <span className="override-audit__reason">{localQ.override_reason}</span>
              {localQ.overridden_by && (
                <span className="override-audit__by">by {localQ.overridden_by}</span>
              )}
            </div>
          )}

          <ScoreOverridePanel
            interviewId={interviewId}
            questionNumber={localQ.question_number}
            originalScore={localQ.original_score ?? localQ.score}
            currentOverride={localQ.override_score}
            maxScore={localQ.max_score}
            roundNumber={roundNumber}
            onOverrideApplied={handleOverrideApplied}
            onToast={onToast}
          />
        </div>
      )}
    </div>
  );
}
