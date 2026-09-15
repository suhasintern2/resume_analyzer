import { getInitials } from '../utils';
import { FileIconSmall } from './Icons';

function CandidateProfile({ candidateName, summary, totalQuestions, categoryCount, interviewId }) {
  const name = candidateName || 'Candidate';
  const initials = getInitials(name);

  return (
    <div className="card candidate-profile-card">
      <div className="profile-header-row">
        <div className="profile-avatar-block">
          <div className="profile-avatar" id="candidate-avatar">{initials}</div>
          <div className="profile-identity">
            <div className="profile-badge-row">
              <span className="badge-role">Interview Kit Ready</span>
              <span className="badge-tech">Web Developer Evaluation</span>
              {interviewId && (
                <span
                  className="badge-role"
                  style={{ fontFamily: 'monospace', letterSpacing: '0.04em', background: 'var(--brand-primary-surface)', color: 'var(--brand-primary-text)', border: '1px solid var(--brand-primary-border)' }}
                  title="Interview ID — find this in the Dashboard"
                >
                  {interviewId}
                </span>
              )}
            </div>
            <h2 className="candidate-name" id="result-name">{name}</h2>
          </div>
        </div>

        <div className="profile-stats-grid">
          <div className="stat-pill">
            <span className="stat-number" id="stat-total-q">{totalQuestions || 0}</span>
            <span className="stat-label">Questions</span>
          </div>
          <div className="stat-pill">
            <span className="stat-number" id="stat-categories-count">{categoryCount || 6}</span>
            <span className="stat-label">Categories</span>
          </div>
          <div className="stat-pill">
            <span className="stat-number">100%</span>
            <span className="stat-label">Targeted</span>
          </div>
        </div>
      </div>

      <div className="summary-box">
        <div className="summary-title-row">
          <FileIconSmall width="18" height="18" />
          <span>Candidate Profile Summary</span>
        </div>
        <p className="summary-body" id="result-summary">
          {summary || 'Summary not available.'}
        </p>
      </div>
    </div>
  );
}

export default CandidateProfile;