import { CheckIcon } from './Icons';

function getStepClass(stepIndex, stage, done) {
  if (done) return 'completed';
  if (stepIndex === 1) return stage >= 1 ? 'completed' : '';
  if (stepIndex === 2) return stage >= 3 ? 'completed' : stage >= 2 ? 'active' : '';
  if (stepIndex === 3) return stage >= 4 ? 'completed' : stage >= 3 ? 'active' : '';
  if (stepIndex === 4) return stage >= 4 ? 'active' : '';
  return '';
}

function getWidth(stage, done) {
  if (done) return '100%';
  const widths = { 1: '25%', 2: '50%', 3: '75%', 4: '95%' };
  return widths[stage] || '25%';
}

function LoadingSection({ stepStage, stepDone, hidden }) {
  const cls = hidden ? 'card loading-card hidden' : 'card loading-card';

  return (
    <section id="loading-section" className={cls}>
      <div className="loading-header">
        <div className="loading-spinner"></div>
        <div className="loading-titles">
          <h2>Analyzing Resume &amp; Synthesizing Questions</h2>
          <p className="loading-sub">
            Processing candidate qualifications through VlookUp evaluation intelligence...
          </p>
        </div>
      </div>

      <div className="stepper">
        <div className="stepper-track">
          <div
            className="stepper-fill"
            id="stepper-progress-fill"
            style={{ width: getWidth(stepStage, stepDone) }}
          ></div>
        </div>
        <div className="stepper-steps">
          <div className={`step-item ${getStepClass(1, stepStage, stepDone)}`} id="step-upload">
            <div className="step-indicator">
              <CheckIcon className="check-svg" />
            </div>
            <div className="step-text">
              <span className="step-label">Upload</span>
              <span className="step-caption">File Verified</span>
            </div>
          </div>

          <div className={`step-item ${getStepClass(2, stepStage, stepDone)}`} id="step-extract">
            <div className="step-indicator">
              <span className="pulse-dot"></span>
            </div>
            <div className="step-text">
              <span className="step-label">Extraction</span>
              <span className="step-caption">OCR &amp; Document Parsing</span>
            </div>
          </div>

          <div className={`step-item ${getStepClass(3, stepStage, stepDone)}`} id="step-generate">
            <div className="step-indicator">
              <span className="pulse-dot"></span>
            </div>
            <div className="step-text">
              <span className="step-label">Synthesis</span>
              <span className="step-caption">Curating 20 Questions</span>
            </div>
          </div>

          <div className={`step-item ${getStepClass(4, stepStage, stepDone)}`} id="step-format">
            <div className="step-indicator">
              <span className="pulse-dot"></span>
            </div>
            <div className="step-text">
              <span className="step-label">Delivery</span>
              <span className="step-caption">Packaging Q&amp;A Kit</span>
            </div>
          </div>
        </div>
      </div>

      <div className="loading-footer">
        <span className="loading-hint">
          Estimated processing time: 5-15 seconds. Please do not close this window.
        </span>
      </div>
    </section>
  );
}

export default LoadingSection;