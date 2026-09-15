import { useState } from 'react';
import { getCategoryClass } from '../utils';
import {
  CheckIcon,
  ChevronIcon,
  CopyIcon,
  MessageIcon,
} from './Icons';

function QuestionCard({ q, allCollapsed, viewMode, onToast }) {
  const [open, setOpen] = useState(!allCollapsed);
  const [copied, setCopied] = useState(false);

  const isHrMode = viewMode === 'hr';
  const answerHeader = isHrMode
    ? 'What to Look For (Plain-English HR Evaluation Guide)'
    : 'Expected Technical Answer & Architecture Key';
  const answerContent = isHrMode && q.hr_answer ? q.hr_answer : q.answer;

  const numStr = q.number < 10 ? `Q0${q.number}` : `Q${q.number}`;
  const catTagClass = getCategoryClass(q.category);

  const copyToClipboard = async () => {
    try {
      let text = `Question ${q.number} [${q.category}]:\n${q.question}\n`;
      if (q.options && q.options.length > 0) {
        text += 'Options:\n' + q.options.map((o) => `  ${o}`).join('\n') + '\n';
      }
      if (q.correct_option) {
        text += `Correct Option: ${q.correct_option}\n`;
      }
      text += `\nTechnical Answer:\n${q.answer}\n`;
      if (q.hr_answer) {
        text += `\nHR Plain-English Guide:\n${q.hr_answer}\n`;
      }

      await navigator.clipboard.writeText(text);
      setCopied(true);
      onToast(`Copied Q${q.number} to clipboard`);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      onToast('Unable to copy to clipboard.');
    }
  };

  return (
    <div
      className={`q-card${open ? '' : ' collapsed'}`}
      data-num={q.number}
    >
      <div className="q-header" onClick={() => setOpen((o) => !o)}>
        <div className="q-meta-row">
          <div className="q-meta-left">
            <span className="q-num-pill">{numStr}</span>
            <span className={`q-cat-tag ${catTagClass}`}>{q.category}</span>
          </div>
          <div className="q-actions" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className={`card-action-btn${copied ? ' copied' : ''}`}
              onClick={copyToClipboard}
              title="Copy question & answer"
            >
              {copied ? (
                <>
                  <CheckIcon width="14" height="14" strokeWidth="3" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <CopyIcon width="14" height="14" />
                  <span>Copy</span>
                </>
              )}
            </button>
            <button
              type="button"
              className="card-action-btn"
              onClick={() => setOpen((o) => !o)}
              title="Toggle Answer"
            >
              <ChevronIcon className="chevron-icon" />
            </button>
          </div>
        </div>
        <h4 className="q-title">{q.question}</h4>
        {q.options && q.options.length > 0 && (
          <div className="mcq-options-container">
            {q.options.map((opt, idx) => {
              const optTrim = opt.trim();
              const isOptionCorrect =
                q.correct_option &&
                optTrim.toUpperCase().startsWith(q.correct_option.toUpperCase());
              return (
                <div
                  key={`${q.number}-opt-${idx}`}
                  className={`mcq-opt-pill${isOptionCorrect ? ' is-correct' : ''}`}
                >
                  <span>{opt}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="q-answer-container">
        <div className={`q-answer-callout${isHrMode ? ' hr-mode' : ''}`}>
          {q.correct_option && (
            <div className="mcq-key-badge">
              <CheckIcon width="12" height="12" strokeWidth="3" />
              <span>Correct Option: {q.correct_option}</span>
            </div>
          )}
          <div className="answer-header">
            <MessageIcon width="14" height="14" />
            <span>{answerHeader}</span>
          </div>
          <div className="answer-text">{answerContent}</div>
        </div>
      </div>
    </div>
  );
}

export default QuestionCard;