/**
 * DashboardPage — Interview Management Dashboard.
 *
 * Shows all interviews created via the home-page upload flow. Each card
 * has document download buttons and an answer-script upload control.
 * Resume upload happens ONLY on the home page — there is no resume upload
 * on this page.
 *
 * Polls GET /api/interviews every VITE_JOB_POLL_INTERVAL_SECONDS seconds
 * (default 3s). Polling stops automatically once every visible interview
 * is in a terminal state (COMPLETED, FAILED, EVALUATED, EVALUATION_FAILED).
 * No fake progress percentages — only real DB stages shown.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { listInterviews } from '../services/api';
import InterviewCard from './InterviewCard';
import Toast from './Toast';

// Env var injected by Vite at build time. Falls back to 3 seconds.
const POLL_INTERVAL_MS = (
  parseFloat(import.meta.env.VITE_JOB_POLL_INTERVAL_SECONDS || '3') * 1000
);

const TERMINAL_STATUSES = new Set([
  'COMPLETED', 'FAILED', 'EVALUATED', 'EVALUATION_FAILED',
]);

// Statuses that have generated documents worth fetching
const DOCS_STATUSES = new Set([
  'COMPLETED', 'ANSWER_UPLOADED', 'SEGMENTED', 'SEGMENTATION_UNCERTAIN',
  'EVALUATING', 'EVALUATED', 'EVALUATION_FAILED',
]);

export default function DashboardPage({ onBack }) {
  const [interviews, setInterviews]     = useState([]);
  const [documentsMap, setDocumentsMap] = useState({}); // interview_id -> docs[]
  const [loading, setLoading]           = useState(true);
  const [loadError, setLoadError]       = useState('');
  const [toast, setToast]               = useState({ message: '', visible: false });

  // Score / sort toolbar state
  const [sortBy, setSortBy]     = useState('newest');
  const [minScore, setMinScore] = useState('');
  const [top10Only, setTop10Only] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const toastTimerRef = useRef(null);
  const pollRef       = useRef(null);

  // ── Toast ─────────────────────────────────────────────────────────────────
  const showToast = useCallback((message) => {
    clearTimeout(toastTimerRef.current);
    setToast({ message, visible: true });
    toastTimerRef.current = setTimeout(
      () => setToast((t) => ({ ...t, visible: false })),
      2800,
    );
  }, []);

  useEffect(() => () => {
    clearTimeout(toastTimerRef.current);
    clearInterval(pollRef.current);
  }, []);

  // ── Document loading ──────────────────────────────────────────────────────
  // Fetch documents once per interview that has them, cache the result.
  // Errors here are non-fatal and never pollute the main loadError state.
  const fetchDocumentsFor = useCallback(async (iv) => {
    if (!DOCS_STATUSES.has(iv.status)) return;
    try {
      const res = await fetch(
        `/api/interviews/${encodeURIComponent(iv.interview_id)}/documents`,
      );
      if (!res.ok) return; // no documents yet for this interview — silently skip
      const data = await res.json();
      setDocumentsMap((prev) => ({
        ...prev,
        [iv.interview_id]: data.documents || [],
      }));
    } catch {
      // Non-fatal: document list is best-effort, never blocks the dashboard
    }
  }, []);

  // ── Fetch interview list ──────────────────────────────────────────────────
  const fetchInterviews = useCallback(async () => {
    try {
      const { interviews: list } = await listInterviews();
      const arr = list || [];
      setInterviews(arr);
      setLoadError('');

      // Lazily load documents for interviews that should have them,
      // skipping ones we already fetched.
      arr.forEach((iv) => {
        setDocumentsMap((prev) => {
          if (prev[iv.interview_id] !== undefined) return prev; // already cached
          // Kick off fetch asynchronously — does not block state update
          fetchDocumentsFor(iv);
          return prev;
        });
      });
    } catch (err) {
      setLoadError(err.message || 'Failed to load interviews.');
    } finally {
      setLoading(false);
    }
  }, [fetchDocumentsFor]);

  // ── Polling ───────────────────────────────────────────────────────────────
  const allTerminal = useMemo(
    () => interviews.length > 0 && interviews.every((iv) => TERMINAL_STATUSES.has(iv.status)),
    [interviews],
  );

  // Initial load on mount
  useEffect(() => {
    fetchInterviews();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling loop — restarts whenever allTerminal changes
  useEffect(() => {
    clearInterval(pollRef.current);
    if (allTerminal) return;

    pollRef.current = setInterval(fetchInterviews, POLL_INTERVAL_MS);
    return () => clearInterval(pollRef.current);
  }, [allTerminal, fetchInterviews]);

  // Manual refresh — used by child cards after upload / evaluate actions
  const handleRefresh = useCallback(() => {
    // Clear document cache so newly generated docs appear on next fetch
    setDocumentsMap({});
    fetchInterviews();
  }, [fetchInterviews]);

  // ── Score filter / sort / top-10 (client-side) ─────────────────────────
  const minScoreNum = parseFloat(minScore);
  const isFiltering = (
    top10Only ||
    (!Number.isNaN(minScoreNum) && minScoreNum > 0) ||
    sortBy !== 'newest'
  );

  const visibleInterviews = useMemo(() => {
    let list = [...interviews];

    const min = parseFloat(minScore);
    if (!Number.isNaN(min) && min > 0) {
      list = list.filter(
        (iv) => iv.percentage != null && Number(iv.percentage) >= min,
      );
    }

    if (top10Only) {
      list = list
        .filter((iv) => iv.percentage != null)
        .sort((a, b) => Number(b.percentage) - Number(a.percentage))
        .slice(0, 10);
    }

    const pct = (iv) => (iv.percentage == null ? -1 : Number(iv.percentage));
    switch (sortBy) {
      case 'score_desc':
        list.sort((a, b) => pct(b) - pct(a));
        break;
      case 'score_asc':
        list.sort((a, b) => pct(a) - pct(b));
        break;
      case 'name':
        list.sort((a, b) => (a.candidate_name || '').localeCompare(b.candidate_name || ''));
        break;
      default: // 'newest' — API already returns newest-first
        break;
    }
    return list;
  }, [interviews, minScore, top10Only, sortBy]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <section className="dashboard-page">

      {/* ── Top bar ── */}
      <div className="dashboard-page__topbar">
        <div className="dashboard-page__heading">
          <h2 className="dashboard-page__title">Interview Dashboard</h2>
          {allTerminal && interviews.length > 0 && (
            <span className="badge badge-success badge-sm">
              All complete — polling paused
            </span>
          )}
          {!allTerminal && interviews.length > 0 && (
            <span className="badge badge-info badge-sm pulse">
              Auto-refreshing every {Math.round(POLL_INTERVAL_MS / 1000)}s
            </span>
          )}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onBack}>
          ← Back to Upload
        </button>
      </div>

      {/* ── Info banner — replaces the removed upload box ── */}
      <div className="dashboard-info-banner">
        <span className="dashboard-info-banner__icon">ℹ</span>
        <span>
          Interviews are created from the{' '}
          <button className="btn-link" onClick={onBack}>home page upload</button>.
          Use the cards below to download documents, upload answer scripts, and view evaluation scores.
        </span>
      </div>

      {/* ── Filter / sort / top-10 toolbar ── */}
      {interviews.length > 0 && (
        <div className="dashboard-toolbar">
          <div className="dashboard-toolbar__controls">
            <button
              className={`btn btn-sm ${showFilters ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setShowFilters((v) => !v)}
            >
              {showFilters ? '▲ Hide filter' : '▼ Filter by score'}
            </button>
            <button
              className={`btn btn-sm ${top10Only ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setTop10Only((v) => !v)}
            >
              Top 10 scores
            </button>
            <select
              className="dashboard-toolbar__sort"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="newest">Sort: Newest</option>
              <option value="score_desc">Sort: Score ↓</option>
              <option value="score_asc">Sort: Score ↑</option>
              <option value="name">Sort: Name A→Z</option>
            </select>
            {isFiltering && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setMinScore('');
                  setTop10Only(false);
                  setSortBy('newest');
                }}
              >
                Clear filters
              </button>
            )}
          </div>

          {showFilters && (
            <div className="dashboard-toolbar__filters">
              <label className="dashboard-toolbar__label" htmlFor="min-score">
                Show only candidates scoring at least:
              </label>
              <div className="dashboard-toolbar__min-score">
                <input
                  id="min-score"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="e.g. 50"
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                />
                <span>%</span>
                {minScore !== '' && (
                  <button className="btn btn-ghost btn-xs" onClick={() => setMinScore('')}>
                    Clear
                  </button>
                )}
              </div>
            </div>
          )}

          {isFiltering && (
            <span className="badge badge-sm badge-success dashboard-toolbar__count">
              Showing {visibleInterviews.length} of {interviews.length}
            </span>
          )}
        </div>
      )}

      {/* ── Interview list ── */}
      <div className="dashboard-interviews">
        {loading && (
          <div className="dashboard-interviews__loading">Loading interviews…</div>
        )}

        {loadError && !loading && (
          <div className="dashboard-interviews__error">
            {loadError}
            <button className="btn btn-ghost btn-xs" onClick={handleRefresh}>
              Retry
            </button>
          </div>
        )}

        {!loading && !loadError && interviews.length === 0 && (
          <div className="dashboard-interviews__empty">
            <p>No interviews yet. Upload a resume on the home page to get started.</p>
          </div>
        )}

        {!loading && !loadError && interviews.length > 0 && visibleInterviews.length === 0 && (
          <div className="dashboard-interviews__empty">
            <p>No interviews match the current filter. Clear or adjust the filters above.</p>
          </div>
        )}

        {visibleInterviews.map((iv) => (
          <InterviewCard
            key={iv.interview_id}
            interview={iv}
            documents={documentsMap[iv.interview_id] || []}
            onToast={showToast}
            onRefresh={handleRefresh}
          />
        ))}
      </div>

      <Toast message={toast.message} visible={toast.visible} />
    </section>
  );
}
