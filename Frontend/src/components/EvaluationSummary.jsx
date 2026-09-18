/**
 * EvaluationSummary — shows overall score and per-question breakdown.
 * Pulls the current evaluation from the backend via getEvaluation().
 * Handles EVALUATING (in-progress) and EVALUATED states.
 */
import { useCallback, useEffect, useState } from 'react';
import { getEvaluation } from '../services/api';
import QuestionEvaluation from './QuestionEvaluation';

export default function EvaluationSummary({
  interviewId,
  status,
  onToast,
}) {
  const [evalData, setEvalData] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const fetch = useCallback(async () => {
    if (!['EVALUATED', 'EVALUATING', 'EVALUATION_FAILED'].includes(status)) return;
    setLoading(true);
    setError('');
    try {
      const data = await getEvaluation(interviewId);
      setEvalData(data);
    } catch (err) {
      if (!err.message.includes('No evaluation found')) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [interviewId, status]);

  useEffect(() => { fetch(); }, [fetch]);

  if (status === 'EVALUATING') {
    return (
      <div className="evaluation-summary evaluation-summary--pending">
        <div className="evaluation-summary__title">Evaluation in progress…</div>
        <p className="evaluation-summary__desc">
          The deterministic evaluator is scoring the answers. This page will update automatically.
        </p>
      </div>
    );
  }

  if (loading) return <div className="evaluation-summary evaluation-summary--loading">Loading evaluation…</div>;
  if (error)   return <div className="evaluation-summary evaluation-summary--error">Error: {error}</div>;
  if (!evalData) return null;

  const { total_score, max_score, percentage, questions = [] } = evalData;

  return (
    <div className="evaluation-summary">
      {/* Overall score headline */}
      <div className="evaluation-summary__headline">
        <div className="score-display">
          <span className="score-display__value">
            {total_score != null ? Number(total_score).toFixed(1) : '—'}
          </span>
          <span className="score-display__divider">/</span>
          <span className="score-display__max">
            {max_score != null ? Number(max_score).toFixed(0) : '—'}
          </span>
        </div>
        <div className="score-display__pct">
          {percentage != null ? `${Number(percentage).toFixed(1)}%` : '—'}
        </div>
        <div className="score-display__version">
          Evaluator: {evalData.evaluator_version}
        </div>
      </div>

      {/* Per-question breakdown */}
      {questions.length > 0 && (
        <div className="evaluation-questions">
          <div className="evaluation-questions__title">Question Breakdown</div>
          {questions.map((q) => (
            <QuestionEvaluation
              key={q.question_number}
              q={q}
              interviewId={interviewId}
              onOverrideApplied={() => fetch()}
              onToast={onToast}
            />
          ))}
        </div>
      )}

      {questions.length === 0 && (
        <p className="evaluation-summary__empty">No question results available.</p>
      )}
    </div>
  );
}
