/**
 * DocumentActions — download buttons for question_sheet, answer_key,
 * role-specific DOCX (interviewer / hr / candidate), and PDF.
 */
import { useState } from 'react';
import { downloadInterviewDocument, downloadRoleDocx, downloadInterviewPDF } from '../services/api';

const DOC_LABELS = {
  question_sheet: 'Question Sheet',
  answer_key:     'Answer Key',
};

const ROLE_DOCS = [
  { role: 'interviewer', label: '↓ Interviewer DOCX' },
  { role: 'hr',          label: '↓ HR DOCX' },
  { role: 'candidate',   label: '↓ Candidate DOCX' },
];

const PDF_ROLES = [
  { role: 'interviewer', label: '↓ Interviewer PDF' },
  { role: 'hr',          label: '↓ HR PDF' },
];

export default function DocumentActions({
  interviewId,
  documents = [],
  onToast,
}) {
  const [downloading, setDownloading] = useState(null);

  async function handleDownload(fileType) {
    setDownloading(fileType);
    try {
      const blob = await downloadInterviewDocument(
        interviewId,
        fileType,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VlookUp_${DOC_LABELS[fileType] || fileType}_${interviewId}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onToast?.(`Downloaded ${DOC_LABELS[fileType] || fileType}`);
    } catch (err) {
      onToast?.(`Download failed: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  }

  async function handleRoleDownload(role) {
    setDownloading(role);
    try {
      const blob = await downloadRoleDocx(interviewId, role);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VlookUp_${role.charAt(0).toUpperCase() + role.slice(1)}_${interviewId}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onToast?.(`Downloaded ${role} DOCX`);
    } catch (err) {
      onToast?.(`Download failed: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  }

  async function handlePdfDownload(role) {
    setDownloading(role);
    try {
      const blob = await downloadInterviewPDF(interviewId, role);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VlookUp_${role.charAt(0).toUpperCase() + role.slice(1)}_${interviewId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onToast?.(`Downloaded ${role} PDF`);
    } catch (err) {
      onToast?.(`PDF download failed: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="document-actions">
      {documents.map(({ file_type }) => (
        <button
          key={file_type}
          className="btn btn-outline btn-sm"
          disabled={downloading === file_type}
          onClick={() => handleDownload(file_type)}
          title={`Download ${DOC_LABELS[fileType] || fileType}`}
        >
          {downloading === file_type ? 'Downloading…' : `↓ ${DOC_LABELS[fileType] || fileType}`}
        </button>
      ))}
      {ROLE_DOCS.map(({ role, label }) => (
        <button
          key={role}
          className="btn btn-primary btn-sm"
          disabled={downloading === role}
          onClick={() => handleRoleDownload(role)}
          title={`Download ${role} DOCX`}
        >
          {downloading === role ? 'Downloading…' : label}
        </button>
      ))}
      {PDF_ROLES.map(({ role, label }) => (
        <button
          key={role}
          className="btn btn-accent btn-sm"
          disabled={downloading === role}
          onClick={() => handlePdfDownload(role)}
          title={`Download ${role} PDF`}
        >
          {downloading === role ? 'Downloading…' : label}
        </button>
      ))}
    </div>
  );
}