import { useRef, useState } from 'react';
import { formatBytes } from '../utils';
import {
  AlertIcon,
  CameraIcon,
  LightningIcon,
  TrashIcon,
  UploadIcon,
  UploadIconBig,
  FileIcon,
} from './Icons';

function UploadSection({
  hidden,
  selectedFile,
  onFileSelect,
  onClearFile,
  onGenerate,
  generateDisabled,
  error,
  onGoToMCQ,
}) {
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const pickFromInput = (input) => {
    if (input.files.length > 0) {
      onFileSelect(input.files[0]);
    }
    input.value = '';
  };

  return (
    <section id="upload-section" className={hidden ? 'card upload-card hidden' : 'card upload-card'}>
      <div
        className={dragActive ? 'upload-dropzone drag-active' : 'upload-dropzone'}
        id="upload-area"
        onClick={() => fileInputRef.current && fileInputRef.current.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          const files = e.dataTransfer.files;
          if (files.length > 0) {
            onFileSelect(files[0]);
          }
        }}
      >
        <div className="dropzone-icon-wrap">
          <UploadIconBig className="dropzone-icon" />
        </div>
        <div className="dropzone-text">
          <h2 className="dropzone-heading">Select or Drop Resume Document</h2>
          <p className="dropzone-sub">Upload candidate resume as PDF or capture a photo/scanned copy</p>
        </div>

        <div className="dropzone-badges">
          <span className="format-badge">PDF</span>
          <span className="format-badge">PNG</span>
          <span className="format-badge">JPG / JPEG</span>
          <span className="format-badge limit-badge">Max 4 MB</span>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          id="file-input"
          accept=".pdf,.jpg,.jpeg,.png"
          hidden
          onChange={(e) => e.target.files.length > 0 && onFileSelect(e.target.files[0])}
        />
        <input
          ref={cameraInputRef}
          type="file"
          id="camera-input"
          accept="image/jpeg,image/png"
          capture="environment"
          hidden
          onChange={(e) => pickFromInput(e.target)}
        />

        <div className="dropzone-actions" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="btn btn-primary"
            id="choose-btn"
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
          >
            <UploadIcon />
            Browse Files
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            id="camera-btn"
            onClick={() => cameraInputRef.current && cameraInputRef.current.click()}
          >
            <CameraIcon />
            Capture via Camera
          </button>
        </div>
      </div>

      {selectedFile ? (
        <div className="file-preview-card" id="file-info">
          <div className="file-preview-left">
            <div className="file-type-icon" id="file-type-icon">
              <FileIcon />
            </div>
            <div className="file-meta">
              <span className="file-label">Ready for Analysis</span>
              <div className="file-name-row">
                <strong id="file-name">{selectedFile.name}</strong>
                <span className="file-size" id="file-size">{formatBytes(selectedFile.size)}</span>
              </div>
            </div>
          </div>
          <div className="file-preview-actions">
            <button
              type="button"
              className="btn btn-primary btn-generate"
              id="generate-btn"
              onClick={onGenerate}
              disabled={generateDisabled}
            >
              <LightningIcon />
              Generate Interview Q&amp;A
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              id="change-file-btn"
              title="Choose another file"
              onClick={onClearFile}
            >
              <TrashIcon />
              Remove
            </button>
          </div>
        </div>
      ) : (
        <></>
      )}

      <div className={error ? 'alert-box error-alert' : 'alert-box error-alert hidden'} id="error-message">
        <AlertIcon className="alert-icon" />
        <div className="alert-content" id="error-text">{error}</div>
      </div>

      {/* Task 13 — MCQ Question Bank */}
      <div className="mcq-bank__home-btn">
        <button
          type="button"
          className="btn btn-primary btn-mcq"
          id="mcq-round-btn"
          onClick={onGoToMCQ}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
          </svg>
          Round 1 — MCQ Question Bank
        </button>
      </div>
    </section>
  );
}

export default UploadSection;