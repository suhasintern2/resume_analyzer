import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getMCQDays,
  getMCQDay,
  downloadMCQPaper,
  uploadMCQAnswers,
  getMCQResults,
  downloadMCQAnswerKey,
} from '../services/api';

const DAYS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export default function MCQBank({ onToast, onBack }) {
  const [phase, setPhase] = useState('days');
  const [_days, setDays] = useState([]);
  const [selectedDay, setSelectedDay] = useState(null);
  const [dayQuestions, setDayQuestions] = useState([]);
  const [correctAnswers, setCorrectAnswers] = useState([]);
  const [downloading, setDownloading] = useState(false);
  const [downloadingAnswerKey, setDownloadingAnswerKey] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [scores, setScores] = useState(null);
  const [completedDays, setCompletedDays] = useState(new Set());

  const fileInputRef = useRef(null);
  const toastTimerRef = useRef(null);

  const showToast = useCallback((message) => {
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {}, 2400);
    onToast?.(message);
  }, [onToast]);

  useEffect(() => () => clearTimeout(toastTimerRef.current), []);

  // Reset correctAnswers when leaving day-selected phase
  useEffect(() => {
    if (phase !== 'day-selected' || !selectedDay) {
      setCorrectAnswers([]);
    }
  }, [phase, selectedDay]);

  useEffect(() => {
    async function loadDays() {
      try {
        const { days: dayList } = await getMCQDays();
        setDays(dayList);
      } catch {
        showToast('Failed to load MCQ days.');
      }
    }
    loadDays();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleDaySelect(day) {
    if (completedDays.has(day)) {
      showToast(`Day ${day} already completed. Move to next day.`);
      return;
    }
    const expectedDay = selectedDay ? selectedDay + 1 : 1;
    if (day !== expectedDay && day !== 1) {
      showToast(`Please complete Day ${expectedDay - 1} first.`);
      return;
    }
    setSelectedDay(day);
    setPhase('day-selected');
    setScores(null);
    setUploadError('');
    setSelectedFiles([]);
    try {
      const status = await getMCQDay(day);
      setDayQuestions(status.questions || []);
      // Also fetch and set the correct answers for display
      const results = await getMCQResults(day);
      setCorrectAnswers(results.correct_answers || []);
    } catch (err) {
      setDayQuestions([]);
      setCorrectAnswers([]);
      showToast(err.message || 'Failed to load day questions.');
    }
  }

  async function handleDownload() {
    if (!selectedDay) return;
    setDownloading(true);
    try {
      const blob = await downloadMCQPaper(selectedDay);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VlookUp_MCQ_Paper_Day_${selectedDay}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      showToast(`Day ${selectedDay} question paper downloaded!`);
    } catch (err) {
      showToast('Failed to download question paper.');
    } finally {
      setDownloading(false);
    }
  }

  async function handleDownloadAnswerKey() {
    if (!selectedDay) return;
    setDownloadingAnswerKey(true);
    try {
      const blob = await downloadMCQAnswerKey(selectedDay);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VlookUp_MCQ_Answer_Key_Day_${selectedDay}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      showToast(`Day ${selectedDay} answer key downloaded!`);
    } catch (err) {
      showToast('Failed to download answer key.');
    } finally {
      setDownloadingAnswerKey(false);
    }
  }

  async function handleUpload() {
    if (!selectedDay || !selectedFiles.length) return;
    setUploading(true);
    setUploadError('');
    try {
      const result = await uploadMCQAnswers(selectedDay, selectedFiles);
      const candidateScores = result.scores || {};
      setScores(candidateScores);
      setCompletedDays((prev) => new Set([...prev, selectedDay]));
      try {
        const results = await getMCQResults(selectedDay);
        setCorrectAnswers(results.correct_answers || []);
      } catch { /* ignore */ }
      setPhase('results');
      showToast(`Day ${selectedDay} scored! Check results below.`);
    } catch (err) {
      setUploadError(err.message || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  }

  function handleFilePick(e) {
    const files = Array.from(e.target.files || []);
    setSelectedFiles((prev) => [...prev, ...files]);
    setUploadError('');
  }

  function handleDrop(e) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files || []);
    setSelectedFiles((prev) => [...prev, ...files]);
    setUploadError('');
  }

  function removeFile(index) {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }

  const canProceedToNextDay = completedDays.has(selectedDay);
  const nextDay = selectedDay ? selectedDay + 1 : 1;
  const lastDay = 10;

  return (
    <section className="mcq-bank">
      <div className="mcq-bank__header">
        <div className="mcq-bank__heading">
          <h2>MCQ Question Bank — Round 1</h2>
          <p>Select a day to download the question paper, collect candidate answers, upload and score.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onBack}>
          ← Back to Upload
        </button>
      </div>

      <div className="mcq-bank__progress">
        <div className="mcq-bank__progress-bar">
          <div
            className="mcq-bank__progress-fill"
            style={{ width: `${(completedDays.size / DAYS.length) * 100}%` }}
          />
        </div>
        <span className="mcq-bank__progress-text">
          {completedDays.size} / {DAYS.length} days completed
        </span>
      </div>

      <div className="mcq-bank__days">
        <h3 className="mcq-bank__section-title">Select a Day</h3>
        <div className="mcq-bank__day-grid">
          {DAYS.map((day) => {
            const isCompleted = completedDays.has(day);
            const isSelected = selectedDay === day;
            const isLocked = day > 1 && !completedDays.has(day - 1);
            const isNext = day === (selectedDay ? selectedDay + 1 : 1);

            return (
              <button
                key={day}
                className={`mcq-bank__day-btn ${isCompleted ? 'mcq-bank__day-btn--completed' : ''} ${isSelected ? 'mcq-bank__day-btn--selected' : ''} ${isLocked ? 'mcq-bank__day-btn--locked' : ''} ${isNext ? 'mcq-bank__day-btn--next' : ''}`}
                onClick={() => handleDaySelect(day)}
                disabled={isLocked && !isCompleted}
                title={isLocked ? `Complete Day ${day - 1} first` : `Day ${day}`}
              >
                <span className="mcq-bank__day-number">{day}</span>
                {isCompleted && <span className="mcq-bank__day-check">✓</span>}
                {isNext && !isCompleted && <span className="mcq-bank__day-next">→</span>}
                {isLocked && <span className="mcq-bank__day-lock">🔒</span>}
              </button>
            );
          })}
        </div>
      </div>

      {selectedDay && phase === 'day-selected' && (
        <div className="mcq-bank__questions">
          <h3 className="mcq-bank__section-title">Day {selectedDay} Questions</h3>
          <div className="mcq-bank__question-list">
            {dayQuestions.length === 0 ? (
              <div className="mcq-bank__no-questions">
                <p>No questions available for Day {selectedDay}.</p>
                <p className="mcq-bank__no-questions-hint">
                  Ensure <code>generated/mcq_bank/mcq_dataset.json</code> exists and has questions
                  in each column with at least {selectedDay} entries per column.
                </p>
              </div>
            ) : (
              dayQuestions.map((q, i) => (
                <div key={i} className="mcq-bank__question-item">
                  <span className="mcq-bank__q-number">Q{i + 1}</span>
                  <span className="mcq-bank__q-text">
                    {q.question || `Question ${i + 1} (${q.category || 'N/A'})`}
                  </span>
                  {q.options && q.options.length > 0 && (
                    <div className="mcq-bank__options">
                      {q.options.map((opt, j) => (
                        <span key={j} className="mcq-bank__option">{opt}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {selectedDay && correctAnswers.length > 0 && (
        <div className="mcq-bank__answer-key-display">
          <div className="mcq-bank__answer-key-label">Answer Key:</div>
          <div className="mcq-bank__answer-key-sequence">
            {correctAnswers.map((answer, index) => (
              <span key={index} className="mcq-bank__answer-key-item">
                {index + 1}.{answer.toLowerCase()}{index === correctAnswers.length - 1 ? '' : ', '}
              </span>
            ))}
          </div>
        </div>
      )}

      {selectedDay && (
        <div className="mcq-bank__actions">
          <button
            className="btn btn-primary me-2"
            onClick={handleDownload}
            disabled={downloading || completedDays.has(selectedDay)}
          >
            {downloading ? 'Downloading…' : `Download Day ${selectedDay} Paper`}
          </button>
          <button
            className="btn btn-outline-primary"
            onClick={handleDownloadAnswerKey}
            disabled={downloadingAnswerKey || completedDays.has(selectedDay)}
          >
            {downloadingAnswerKey ? 'Downloading…' : `Download Day ${selectedDay} Answer Key`}
          </button>

          <div className="mcq-bank__upload">
            <h3 className="mcq-bank__section-title">Upload Completed Answer Sheets</h3>
            <div
              className="upload-dropzone upload-dropzone--compact"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.csv,.pdf,.jpg,.jpeg,.png"
                multiple
                style={{ display: 'none' }}
                onChange={handleFilePick}
              />
              {selectedFiles.length > 0 ? (
                <span className="upload-dropzone__selected">
                  {selectedFiles.length} file(s) selected
                </span>
              ) : (
                <span className="upload-dropzone__hint">
                  Drag &amp; drop or click — answer sheets (5 candidates)
                </span>
              )}
            </div>

            {selectedFiles.length > 0 && (
              <div className="mcq-bank__files">
                {selectedFiles.map((f, i) => (
                  <div key={i} className="mcq-bank__file-item">
                    <span>{f.name}</span>
                    <button className="btn btn-ghost btn-xs" onClick={() => removeFile(i)}>✕</button>
                  </div>
                ))}
              </div>
            )}

            <button
              className="btn btn-primary"
              disabled={!selectedFiles.length || uploading || completedDays.has(selectedDay)}
              onClick={handleUpload}
            >
              {uploading ? 'Uploading…' : `Upload & Score Day ${selectedDay}`}
            </button>
          </div>
        </div>
      )}

      {uploadError && <div className="mcq-bank__error">{uploadError}</div>}

      {phase === 'results' && scores && (
        <div className="mcq-bank__results">
          <h3 className="mcq-bank__section-title">Day {selectedDay} — Results</h3>
          <div className="mcq-bank__results-table">
            <div className="mcq-bank__results-header">
              <span>Candidate</span>
              <span>Score</span>
              <span>Max</span>
              <span>%</span>
            </div>
            {Object.entries(scores).map(([name, data]) => (
              <div key={name} className="mcq-bank__results-row">
                <span className="mcq-bank__candidate-name">{name}</span>
                <span className="mcq-bank__score">{data.score}</span>
                <span className="mcq-bank__max">{data.max_score}</span>
                <span className={`mcq-bank__percentage ${data.percentage >= 70 ? 'mcq-bank__percentage--pass' : 'mcq-bank__percentage--fail'}`}>
                  {data.percentage}%
                </span>
              </div>
            ))}
          </div>

          {correctAnswers.length > 0 && (
            <div className="mcq-bank__answer-key">
              <h4>Answer Key</h4>
              <div className="mcq-bank__key-list">
                {correctAnswers.map((ans, i) => (
                  <div key={i} className="mcq-bank__key-item">
                    <span className="mcq-bank__key-q">Q{i + 1}</span>
                    <span className="mcq-bank__key-ans">{ans}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {selectedDay && phase === 'results' && (
        <div className="mcq-bank__nav">
          {canProceedToNextDay && nextDay <= lastDay && (
            <button
              className="btn btn-primary"
              onClick={() => handleDaySelect(nextDay)}
            >
              Next Day → Day {nextDay}
            </button>
          )}
          {selectedDay === lastDay && (
            <div className="mcq-bank__complete">
              <h3>🎉 All 10 days complete!</h3>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
