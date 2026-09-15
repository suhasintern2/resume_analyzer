/**
 * SegmentationCorrectionView — shown when status is SEGMENTATION_UNCERTAIN.
 * Displays raw OCR blocks and lets staff assign each to a question number.
 * Required before evaluation can run (per spec §13 / amendment §8).
 */
import { useCallback, useEffect, useState } from 'react';
import { getSegments, reassignSegment } from '../services/api';

export default function SegmentationCorrectionView({
  interviewId,
  roundNumber = 1,
  onCorrected,
  onToast,
}) {
  const [segments, setSegments]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [saving, setSaving]           = useState(null); // segment id being saved
  const [overrides, setOverrides]     = useState({});   // { segId: questionNumber }
  const [errors, setErrors]           = useState({});

  const fetchSegments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSegments(interviewId, roundNumber);
      setSegments(data.segments || []);
    } catch (err) {
      onToast?.(`Could not load segments: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [interviewId, roundNumber, onToast]);

  useEffect(() => { fetchSegments(); }, [fetchSegments]);

  function handleNumberChange(segId, value) {
    setOverrides((prev) => ({ ...prev, [segId]: value }));
    setErrors((prev) => ({ ...prev, [segId]: '' }));
  }

  async function handleAssign(seg) {
    const raw = overrides[seg.id] ?? seg.question_number ?? '';
    const num = parseInt(raw, 10);
    if (!num || num < 1) {
      setErrors((prev) => ({ ...prev, [seg.id]: 'Enter a positive question number.' }));
      return;
    }
    setSaving(seg.id);
    try {
      const result = await reassignSegment(
      interviewId,
      seg.id,
      num,
      roundNumber,
    );
      onToast?.(`Segment reassigned to Q${num}.`);
      // Refresh segments
      await fetchSegments();
      // If the whole interview is now SEGMENTED, notify parent
      if (result.matched) {
        onCorrected?.();
      }
    } catch (err) {
      setErrors((prev) => ({ ...prev, [seg.id]: err.message }));
    } finally {
      setSaving(null);
    }
  }

  if (loading) {
    return <div className="segmentation-view segmentation-view--loading">Loading segments…</div>;
  }

  return (
    <div className="segmentation-view">
      <div className="segmentation-view__header">
        <span className="badge badge-warning">Segmentation Uncertain</span>
        <p className="segmentation-view__desc">
          The answer sheet could not be automatically aligned. Assign each block to
          the correct question number before running evaluation.
        </p>
      </div>

      <div className="segmentation-blocks">
        {segments.map((seg) => (
          <div
            key={seg.id}
            className={`segmentation-block${seg.is_manual_override ? ' segmentation-block--corrected' : ''}`}
          >
            <div className="segmentation-block__meta">
              <span className="segmentation-block__detected">
                Detected Q: {seg.original_question_number ?? seg.question_number ?? '—'}
              </span>
              {seg.is_manual_override && (
                <span className="badge badge-success badge-xs">manually assigned</span>
              )}
              <span className={`badge badge-xs badge-${seg.status === 'TRANSCRIBED' ? 'info' : seg.status === 'BLANK' ? 'neutral' : 'error'}`}>
                {seg.status}
              </span>
            </div>

            {/* OCR'd text preview — truncated for readability */}
            <pre className="segmentation-block__content">
              {(seg.content || '').slice(0, 400)}{seg.content?.length > 400 ? '…' : ''}
            </pre>

            <div className="segmentation-block__assign">
              <label htmlFor={`seg-q-${seg.id}`} className="segmentation-block__label">
                Assign to question:
              </label>
              <input
                id={`seg-q-${seg.id}`}
                type="number"
                min="1"
                className="input-small"
                value={overrides[seg.id] ?? seg.question_number ?? ''}
                onChange={(e) => handleNumberChange(seg.id, e.target.value)}
                disabled={saving === seg.id}
              />
              <button
                className="btn btn-primary btn-xs"
                disabled={saving === seg.id}
                onClick={() => handleAssign(seg)}
              >
                {saving === seg.id ? 'Saving…' : 'Assign'}
              </button>
              {errors[seg.id] && (
                <span className="field-error">{errors[seg.id]}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {segments.length === 0 && (
        <p className="segmentation-view__empty">No segments found for this interview.</p>
      )}
    </div>
  );
}
