import { RefreshIcon, PrintIcon, DownloadIcon, UsersIcon, FileIconSmall } from './Icons';

function ExportBar({ onGenerateAgain, onPrint, onDownload, downloadingRole, onGoToDashboard, interviewId }) {
  const downloading = downloadingRole !== null;

  return (
    <div className="export-bar card">
      <div className="export-bar-left">
        <button
          type="button"
          className="btn btn-secondary"
          id="generate-again-btn"
          disabled={downloading}
          onClick={onGenerateAgain}
        >
          <RefreshIcon width="16" height="16" />
          Analyze Another Resume
        </button>
        <button
          type="button"
          className="btn btn-outline"
          id="print-btn"
          disabled={downloading}
          onClick={onPrint}
        >
          <PrintIcon width="16" height="16" />
          Print / PDF
        </button>
        {interviewId && onGoToDashboard && (
          <button
            type="button"
            className="btn btn-outline"
            title={`View ${interviewId} in the Dashboard — upload answer scripts, evaluate, view scores`}
            disabled={downloading}
            onClick={onGoToDashboard}
          >
            📋 View in Dashboard
          </button>
        )}
      </div>

      <div className="export-bar-right">
        <button
          type="button"
          className="btn btn-primary"
          id="download-interviewer-btn"
          title="Download Word DOCX with technical key answers"
          disabled={downloading}
          onClick={() => onDownload('interviewer')}
        >
          {downloadingRole === 'interviewer' ? (
            <>
              <svg className="loading-spinner" width="14" height="14" viewBox="0 0 24 24" style={{ marginRight: 4, display: 'inline-block' }}></svg>
              Downloading...
            </>
          ) : (
            <>
              <DownloadIcon width="16" height="16" />
              <span>Download for Interviewer</span>
            </>
          )}
        </button>

        <button
          type="button"
          className="btn btn-secondary btn-hr-download"
          id="download-hr-btn"
          title="Download Word DOCX with non-technical explanations for HR"
          disabled={downloading}
          onClick={() => onDownload('hr')}
        >
          {downloadingRole === 'hr' ? (
            <>
              <svg className="loading-spinner" width="14" height="14" viewBox="0 0 24 24" style={{ marginRight: 4, display: 'inline-block' }}></svg>
              Downloading...
            </>
          ) : (
            <>
              <UsersIcon width="16" height="16" />
              <span>Download for HR</span>
            </>
          )}
        </button>

        <button
          type="button"
          className="btn btn-secondary btn-candidate-download"
          id="download-candidate-btn"
          title="Download Word DOCX with questions and MCQ options only (no answer keys)"
          disabled={downloading}
          onClick={() => onDownload('candidate')}
        >
          {downloadingRole === 'candidate' ? (
            <>
              <svg className="loading-spinner" width="14" height="14" viewBox="0 0 24 24" style={{ marginRight: 4, display: 'inline-block' }}></svg>
              Downloading...
            </>
          ) : (
            <>
              <FileIconSmall width="16" height="16" />
              <span>Download for Candidate</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default ExportBar;