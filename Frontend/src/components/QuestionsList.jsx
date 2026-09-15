import { groupQuestionsByCategory, getDisplayHeader } from '../utils';
import QuestionCard from './QuestionCard';

function QuestionsList({ questions, allCollapsed, viewMode, onToast }) {
  if (!questions || questions.length === 0) {
    return (
      <div id="result-questions" className="questions-stream">
        <div className="empty-filter-state">
          <h3 className="empty-filter-title">No matching interview questions</h3>
          <p>
            Try clearing your search keyword or switching category tabs to view questions.
          </p>
        </div>
      </div>
    );
  }

  const groups = groupQuestionsByCategory(questions);

  return (
    <div id="result-questions" className="questions-stream">
      {groups.map(({ category, questions: catQuestions }) => (
        <div key={category} className="category-group-wrapper">
          <div className="category-group-header">
            <span className="category-group-title">
              {getDisplayHeader(category)}
            </span>
            <span className="category-group-count">
              {catQuestions.length} Questions
            </span>
          </div>
          {catQuestions.map((q) => (
            <QuestionCard
              key={`${q.number}-${allCollapsed ? 'c' : 'o'}`}
              q={q}
              allCollapsed={allCollapsed}
              viewMode={viewMode}
              onToast={onToast}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export default QuestionsList;