/**
 * ScoreOverridePanel — staff can override a question's deterministic score
 * with a required reason. Stores original score auditably; never overwrites it.
 */
import { useState } from 'react';
import { overrideScore } from '../services/api';

export default function ScoreOverridePanel({
  interviewId,
  questionNumber,
  originalScore,
  currentOverride,
  maxScore,
  roundNumber = 1,
  onOverrideApplied,
  onToast,
}) {
  const [open, setOpen]       = useState(false);
  const [score, setScore]     = useState(currentOverride ?? originalScore ?? '');
  const [reason, setReason]   = useState('');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');

  const max = maxScore ?? 10;

  async function handleApply() {
    const numScore = parseFloat(score);
    if (isNaN(numScore) || numScore < 0 || numScore > max) {
      setError(`Score must be between 0 and ${max}.`);
      return;
    }
    if (!reason.trim()) {
      setError('A reason is required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await overrideScore(
        interviewId,
        questionNumber,
        numScore,
        reason.trim(),
        roundNumber,
      );
      onToast?.(`Q${questionNumber} score overridden: ${numScore}/${max}`);
      onOverrideApplied?.(result);
      setOpen(false);
      setReason('');
    } catch (err) {
      setError(err.message || 'Override failed.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="score-override-panel">
      {!open ? (
        <button
          className="btn btn-ghost btn-xs"
          onClick={() => { setOpen(true); setError(''); }}
          title="Override this question's score"
        >
          ✏ Override score
        </button>
      ) : (
        <div className="score-override-panel__form">
          <div className="score-override-panel__row">
            <label className="score-override-panel__label">
              New score (0 – {max}):
            </label>
            <input
              type="number"
              min="0"
              max={max}
              step="0.5"
              className="input-small"
              value={score}
              onChange={(e) => { setScore(e.target.value); setError(''); }}
              disabled={saving}
            />
          </div>

          <div className="score-override-panel__row">
            <label className="score-override-panel__label">
              Reason (required):
            </label>
            <input
              type="text"
              className="input-medium"
              placeholder="e.g. Answer is correct but uses different terminology"
              value={reason}
              maxLength={200}
              onChange={(e) => { setReason(e.target.value); setError(''); }}
              disabled={saving}
            />
          </div>

          {originalScore !== null && originalScore !== undefined && (
            <div className="score-override-panel__original">
              Original deterministic score: <strong>{originalScore}/{max}</strong>
            </div>
          )}

          {error && <div className="field-error">{error}</div>}

          <div className="score-override-panel__actions">
            <button
              className="btn btn-primary btn-xs"
              disabled={saving}
              onClick={handleApply}
            >
              {saving ? 'Saving…' : 'Apply override'}
            </button>
            <button
              className="btn btn-ghost btn-xs"
              disabled={saving}
              onClick={() => { setOpen(false); setError(''); }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
