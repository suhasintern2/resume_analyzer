/**
 * InterviewCard — one card per interview in the dashboard (single round system).
 * Shows: ID, candidate name, status / documents / uploads, and evaluation summary.
 */
import { useState } from 'react';
import ProcessingStages from './ProcessingStages';
import DocumentActions from './DocumentActions';
import AnswerScriptUpload from './AnswerScriptUpload';
import SegmentationCorrectionView from './SegmentationCorrectionView';
import EvaluationSummary from './EvaluationSummary';
import { startEvaluation, deleteInterview, markAsDone } from '../services/api';

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

export default function InterviewCard({
  interview,
  documents = [],
  onToast,
  onRefresh,
}) {
  const [evaluating, setEvaluating]  = useState(false);
  const [deleting, setDeleting]       = useState(false);
  const [markingDone, setMarkingDone] = useState(false);
  const [showContact, setShowContact] = useState(false);
  const [showEvalDetail, setShowEvalDetail] = useState(false);

  const {
    interview_id, candidate_name, status, processing_stage, error_reason,
    created_at, email, phone,
  } = interview;

  const statusLabel = STATUS_LABELS[status] || status;
  const statusCls   = STATUS_CLASSES[status] || '';
  const isTerminal  = TERMINAL.has(status);
  const hasContact  = Boolean(email || phone);

  const createdDate = created_at
    ? new Date(created_at).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
    : '';

  async function handleEvaluate() {
    setEvaluating(true);
    try {
      await startEvaluation(interview_id);
      onToast?.('Evaluation started.');
      onRefresh?.();
    } catch (err) {
      onToast?.(`Could not start evaluation: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete interview ${interview_id} and all its files? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteInterview(interview_id);
      onToast?.(`Interview ${interview_id} deleted.`);
      onRefresh?.();
    } catch (err) {
      onToast?.(`Could not delete: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  }

  async function handleMarkAsDone() {
    if (!window.confirm(`Mark interview ${interview_id} as done? Generated PDFs will be deleted.`)) return;
    setMarkingDone(true);
    try {
      await markAsDone(interview_id);
      onToast?.(`Interview ${interview_id} marked as done. PDFs deleted.`);
      onRefresh?.();
    } catch (err) {
      onToast?.(`Could not mark as done: ${err.message}`);
    } finally {
      setMarkingDone(false);
    }
  }

  return (
    <div className={`interview-card${isTerminal ? '' : ' interview-card--active'}`}>
      {/* ── Card header ───────────────────────────────────────────────── */}
      <div className="interview-card__header">
        <div className="interview-card__id">
          <span className="interview-card__id-label">{interview_id}</span>
          <span className={`status-badge ${statusCls}`}>{statusLabel}</span>
          <button
            className="btn btn-ghost btn-xs interview-card__delete"
            disabled={deleting}
            onClick={handleDelete}
            title={`Delete interview ${interview_id}`}
          >
            {deleting ? '…' : '✕'}
          </button>
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

        {/* Top-level headline = score when evaluated */}
        {status === 'EVALUATED' && interview.percentage != null && (
          <div className="interview-card__score-summary">
            <span className="score-pill">
              Score: {Number(interview.score ?? 0).toFixed(1)}/{Number(interview.max_score ?? 0).toFixed(0)} &nbsp;·&nbsp; {Number(interview.percentage).toFixed(1)}%
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

      {/* ── Interview Details ───────────────────────────────────────── */}
      <div className="interview-card__details">
        {/* Documents */}
        {documents.length > 0 && (
          <DocumentActions
            interviewId={interview_id}
            documents={documents}
            onToast={onToast}
          />
        )}

        {/* Answer script upload */}
        <AnswerScriptUpload
          interviewId={interview_id}
          status={status}
          onUploaded={onRefresh}
          onToast={onToast}
        />

        {/* Segmentation correction */}
        {(status === 'SEGMENTATION_UNCERTAIN' || status === 'SEGMENTED') && status === 'SEGMENTATION_UNCERTAIN' && (
          <SegmentationCorrectionView
            interviewId={interview_id}
            onCorrected={onRefresh}
            onToast={onToast}
          />
        )}

        {/* Evaluate button */}
        {(status === 'SEGMENTED' || (status === 'SEGMENTATION_UNCERTAIN')) && (
          <div className="interview-card__actions">
            <button
              className="btn btn-primary"
              disabled={evaluating}
              onClick={handleEvaluate}
            >
              {evaluating ? 'Starting…' : 'Evaluate'}
            </button>
          </div>
        )}

        {status === 'EVALUATION_FAILED' && (
          <div className="interview-card__actions">
            <button
              className="btn btn-outline"
              disabled={evaluating}
              onClick={handleEvaluate}
            >
              {evaluating ? 'Starting…' : 'Retry'}
            </button>
          </div>
        )}

        {/* Mark as done button — only visible for COMPLETED interviews */}
        {status === 'COMPLETED' && (
          <div className="interview-card__actions">
            <button
              className="btn btn-success"
              disabled={markingDone}
              onClick={handleMarkAsDone}
            >
              {markingDone ? 'Marking…' : '✓ Mark as Done'}
            </button>
          </div>
        )}

        {/* Evaluation summary */}
        {(status === 'EVALUATED' || status === 'EVALUATING') && (
          <div className="interview-card__eval-toggle">
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowEvalDetail((v) => !v)}
            >
              {showEvalDetail ? '▲ Hide evaluation' : '▼ View evaluation'}
            </button>
            {showEvalDetail && (
              <EvaluationSummary
                interviewId={interview_id}
                status={status}
                onToast={onToast}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}