/**
 * AnswerScriptUpload — upload handwritten answer script pages (Task 12 revision).
 * Accepts PDF/JPG/JPEG/PNG, respects ANSWER_SCRIPT_MAX_FILE_SIZE_MB (10 MB default).
 * Round-aware: uploads are scoped to a round via the `roundNumber` prop (default 1).
 */
import { useRef, useState } from 'react';
import { uploadAnswerScript } from '../services/api';

const ALLOWED_EXTS = ['.pdf', '.jpg', '.jpeg', '.png'];
const MAX_MB = 10;

function validateFiles(files) {
  for (const file of files) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      return `Unsupported file type: ${ext}. Allowed: PDF, JPG, JPEG, PNG.`;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return `File "${file.name}" exceeds the ${MAX_MB} MB limit.`;
    }
  }
  return null;
}

export default function AnswerScriptUpload({
  interviewId,
  roundNumber = 1,
  status,
  onUploaded,
  onToast,
}) {
  const fileInputRef = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const UPLOAD_READY = ['COMPLETED', 'ANSWER_UPLOADED', 'SEGMENTED', 'SEGMENTATION_UNCERTAIN'];
  if (!UPLOAD_READY.includes(status)) return null;

  function handleFilePick(e) {
    const files = Array.from(e.target.files || []);
    setError('');
    const err = validateFiles(files);
    if (err) { setError(err); setSelectedFiles([]); return; }
    setSelectedFiles(files);
  }

  function handleDrop(e) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files || []);
    setError('');
    const err = validateFiles(files);
    if (err) { setError(err); setSelectedFiles([]); return; }
    setSelectedFiles(files);
  }

  async function handleUpload() {
    if (!selectedFiles.length) return;
    setUploading(true);
    setError('');
    try {
      await uploadAnswerScript(interviewId, selectedFiles, roundNumber);
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = '';
      onToast?.(`Answer script uploaded for Round ${roundNumber}.`);
      onUploaded?.();
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="answer-script-upload">
      <div className="answer-script-upload__title">
        Upload Answer Script — Round {roundNumber}
      </div>

      <div
        className="upload-dropzone upload-dropzone--compact"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
        aria-label={`Upload answer script pages for Round ${roundNumber}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          multiple
          style={{ display: 'none' }}
          onChange={handleFilePick}
        />
        {selectedFiles.length > 0 ? (
          <span className="upload-dropzone__selected">
            {selectedFiles.length === 1
              ? selectedFiles[0].name
              : `${selectedFiles.length} pages selected`}
          </span>
        ) : (
          <span className="upload-dropzone__hint">
            Drag &amp; drop or click — PDF, JPG, JPEG or PNG (max {MAX_MB} MB)
          </span>
        )}
      </div>

      {error && <div className="upload-error upload-error--inline">{error}</div>}

      <button
        className="btn btn-primary btn-sm"
        disabled={!selectedFiles.length || uploading}
        onClick={handleUpload}
      >
        {uploading ? 'Uploading…' : 'Upload & Process'}
      </button>
    </div>
  );
}
