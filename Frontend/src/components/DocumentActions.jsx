/**
 * DocumentActions — download buttons for question_sheet and answer_key.
 * Round-aware (Task 12): downloads are scoped to a round; round 2 downloads
 * are disabled when locked (the parent card handles the lock, so this component
 * receives only the relevant round's documents).
 */
import { useState } from 'react';
import { downloadInterviewDocument } from '../services/api';

const DOC_LABELS = {
  question_sheet: 'Question Sheet',
  answer_key:     'Answer Key',
};

export default function DocumentActions({
  interviewId,
  documents = [],
  roundNumber = 1,
  onToast,
}) {
  const [downloading, setDownloading] = useState(null);

  if (!documents || documents.length === 0) return null;

  async function handleDownload(fileType) {
    setDownloading(fileType);
    try {
      const blob = await downloadInterviewDocument(
        interviewId,
        fileType,
        roundNumber,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VlookUp_${DOC_LABELS[fileType] || fileType}_R${roundNumber}_${interviewId}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onToast?.(`Downloaded ${DOC_LABELS[fileType] || fileType} (Round ${roundNumber})`);
    } catch (err) {
      onToast?.(`Download failed: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="document-actions">
      <span className="document-actions__label">Round {roundNumber}:</span>
      {documents.map(({ file_type }) => (
        <button
          key={file_type}
          className="btn btn-outline btn-sm"
          disabled={downloading === file_type}
          onClick={() => handleDownload(file_type)}
          title={`Download Round ${roundNumber} ${DOC_LABELS[file_type] || file_type}`}
        >
          {downloading === file_type ? 'Downloading…' : `↓ ${DOC_LABELS[file_type] || file_type}`}
        </button>
      ))}
    </div>
  );
}
