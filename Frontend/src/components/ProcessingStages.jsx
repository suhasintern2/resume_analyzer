/**
 * ProcessingStages — shows the real pipeline stages for an interview.
 * No fake percentages — only actual status from the DB.
 */

const INTERVIEW_STAGES = [
  { stage: 'EXTRACTING',  label: 'Extracting resume text'    },
  { stage: 'GENERATING',  label: 'Generating interview questions' },
  { stage: 'FORMATTING',  label: 'Generating documents'      },
];

const ANSWER_STAGES = [
  { stage: 'EXTRACTING_ANSWERS', label: 'OCR — reading answer script' },
  { stage: 'EVALUATING_ANSWERS', label: 'Evaluating answers'          },
];

function StepIcon({ done, active, failed }) {
  if (failed) return <span className="stage-icon stage-failed" aria-label="Failed">✗</span>;
  if (done)   return <span className="stage-icon stage-done"   aria-label="Done">✓</span>;
  if (active) return <span className="stage-icon stage-active" aria-label="In progress">●</span>;
  return       <span className="stage-icon stage-pending"      aria-label="Pending">○</span>;
}

/**
 * @param {object}  props
 * @param {string}  props.status           - interviews.status value
 * @param {string|null} props.processingStage - interviews.processing_stage value
 */
export default function ProcessingStages({ status, processingStage }) {
  const s = status || '';
  const ps = processingStage || '';

  // ── Question-generation pipeline ──────────────────────────────────────────
  const isPipeline = ['PROCESSING', 'COMPLETED', 'FAILED',
    'ANSWER_UPLOADED', 'SEGMENTED', 'SEGMENTATION_UNCERTAIN',
    'EVALUATING', 'EVALUATED', 'EVALUATION_FAILED'].includes(s);

  // ── Answer evaluation pipeline ────────────────────────────────────────────
  const isAnswerFlow = ['ANSWER_UPLOADED', 'SEGMENTED', 'SEGMENTATION_UNCERTAIN',
    'EVALUATING', 'EVALUATED', 'EVALUATION_FAILED'].includes(s);

  function stageState(stage) {
    const idx = INTERVIEW_STAGES.findIndex(st => st.stage === stage);
    const curIdx = INTERVIEW_STAGES.findIndex(st => st.stage === ps);

    if (s === 'COMPLETED' || (isPipeline && !['QUEUED','PROCESSING','FAILED'].includes(s))) return 'done';
    if (s === 'FAILED') {
      // The stage we were on when we failed is "failed"; prior ones are done
      if (curIdx > idx) return 'done';
      if (curIdx === idx) return 'failed';
      return 'pending';
    }
    if (s === 'PROCESSING') {
      if (curIdx > idx) return 'done';
      if (curIdx === idx) return 'active';
      return 'pending';
    }
    if (s === 'QUEUED') return 'pending';
    // Any post-pipeline status = all pipeline stages done
    return 'done';
  }

  function answerStageState(stage) {
    if (!isAnswerFlow) return 'pending';
    const idx = ANSWER_STAGES.findIndex(st => st.stage === stage);
    const curIdx = ANSWER_STAGES.findIndex(st => st.stage === ps);

    if (s === 'EVALUATED') return 'done';
    if (s === 'EVALUATION_FAILED') {
      if (curIdx > idx) return 'done';
      if (curIdx === idx) return 'failed';
      return 'pending';
    }
    if (s === 'EVALUATING') {
      if (ps === 'EVALUATING_ANSWERS') {
        if (idx === 0) return 'done'; // EXTRACTING_ANSWERS = already done
        if (idx === 1) return 'active';
      }
      return 'pending';
    }
    if (['SEGMENTED','SEGMENTATION_UNCERTAIN'].includes(s) && stage === 'EXTRACTING_ANSWERS') return 'done';
    if (s === 'ANSWER_UPLOADED' && stage === 'EXTRACTING_ANSWERS' && ps === 'EXTRACTING_ANSWERS') return 'active';
    return 'pending';
  }

  return (
    <div className="processing-stages">
      {/* Question generation stages */}
      <div className="stages-group">
        <div className="stages-group-title">Resume Processing</div>
        {/* Upload step is always done once the interview row exists */}
        <div className="stage-row">
          <StepIcon done />
          <span className="stage-label">Resume uploaded</span>
        </div>
        {INTERVIEW_STAGES.map(({ stage, label }) => {
          const st = stageState(stage);
          return (
            <div className="stage-row" key={stage}>
              <StepIcon done={st === 'done'} active={st === 'active'} failed={st === 'failed'} />
              <span className={`stage-label${st === 'active' ? ' stage-label--active' : ''}`}>
                {label}
              </span>
            </div>
          );
        })}
        {isPipeline && !['QUEUED','PROCESSING','FAILED'].includes(s) && (
          <div className="stage-row">
            <StepIcon done />
            <span className="stage-label">Processing complete</span>
          </div>
        )}
        {s === 'QUEUED' && (
          <div className="stage-row">
            <StepIcon />
            <span className="stage-label stage-label--muted">Queued — waiting for worker</span>
          </div>
        )}
      </div>

      {/* Answer evaluation stages — shown only once answer flow starts */}
      {isAnswerFlow && (
        <div className="stages-group">
          <div className="stages-group-title">Answer Evaluation</div>
          <div className="stage-row">
            <StepIcon done />
            <span className="stage-label">Answer script uploaded</span>
          </div>
          {ANSWER_STAGES.map(({ stage, label }) => {
            const st = answerStageState(stage);
            return (
              <div className="stage-row" key={stage}>
                <StepIcon done={st === 'done'} active={st === 'active'} failed={st === 'failed'} />
                <span className={`stage-label${st === 'active' ? ' stage-label--active' : ''}`}>
                  {label}
                </span>
              </div>
            );
          })}
          {s === 'EVALUATED' && (
            <div className="stage-row">
              <StepIcon done />
              <span className="stage-label">Evaluation complete</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
