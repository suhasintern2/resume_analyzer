import { EyeIcon, CopyIcon, CodeIcon, UserIcon, SearchIcon } from './Icons';

const TABS = [
  { dataCat: 'all', label: 'All Questions', key: 'all' },
  { dataCat: 'MCQ', label: 'MCQs', key: 'mcq' },
  { dataCat: 'Basic Technical', label: 'Basic Technical', key: 'basic' },
  { dataCat: 'Mid Technical (MERN)', label: 'MERN Stack', key: 'mern' },
  { dataCat: 'Resume Skills', label: 'Resume Skills', key: 'skills' },
  { dataCat: 'Project', label: 'Projects', key: 'projects' },
  { dataCat: 'VlookUp Scenario', label: 'VlookUp Scenarios', key: 'scenario' },
];

function Toolbar({
  counts,
  activeCategory,
  onCategoryChange,
  searchQuery,
  onSearchChange,
  onClearSearch,
  allCollapsed,
  onToggleAnswers,
  viewMode,
  onViewModeChange,
  onCopyAll,
  searchMatchCountText,
}) {
  return (
    <div className="toolbar-card">
      <div className="toolbar-top">
        <div className="category-tabs" id="category-tabs" role="tablist">
          {TABS.map(({ dataCat, label, key }) => {
            const isActive = activeCategory === dataCat;
            return (
              <button
                key={dataCat}
                type="button"
                className={`tab-btn${isActive ? ' active' : ''}`}
                data-cat={dataCat}
                onClick={() => onCategoryChange(dataCat)}
              >
                <span>{label}</span>
                <span className="tab-count">{counts[key] ?? 0}</span>
              </button>
            );
          })}
        </div>

        <div className="toolbar-actions">
          <div className="view-mode-pill">
            <button
              type="button"
              className={`view-mode-btn${viewMode === 'technical' ? ' active' : ''}`}
              id="view-mode-tech"
              title="View technical key answers for developers"
              onClick={() => onViewModeChange('technical')}
            >
              <CodeIcon width="13" height="13" />
              <span>Technical Key</span>
            </button>
            <button
              type="button"
              className={`view-mode-btn${viewMode === 'hr' ? ' active' : ''}`}
              id="view-mode-hr"
              title="View plain-English assessment guide for HR"
              onClick={() => onViewModeChange('hr')}
            >
              <UserIcon width="13" height="13" />
              <span>HR Guide</span>
            </button>
          </div>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            id="toggle-answers-btn"
            onClick={onToggleAnswers}
          >
            <EyeIcon width="14" height="14" />
            <span id="toggle-answers-text">{allCollapsed ? 'Expand' : 'Collapse'}</span>
          </button>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            id="copy-all-btn"
            onClick={onCopyAll}
          >
            <CopyIcon width="14" height="14" />
            Copy All
          </button>
        </div>
      </div>

      <div className="toolbar-search-row">
        <div className="search-input-wrap">
          <SearchIcon className="search-icon" />
          <input
            type="text"
            id="question-search-input"
            placeholder="Search questions by technology, keyword, or concept (e.g. React, MongoDB, RBAC, SQL, Auth)..."
            autoComplete="off"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <button
            type="button"
            className={searchQuery ? 'search-clear-btn' : 'search-clear-btn hidden'}
            id="search-clear-btn"
            onClick={onClearSearch}
          >
            &times;
          </button>
        </div>
        <div className="search-match-count" id="search-match-count">{searchMatchCountText}</div>
      </div>
    </div>
  );
}

export default Toolbar;