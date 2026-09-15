/**
 * Header — app branding + navigation.
 * Accepts optional `onDashboard` and `onHome` callbacks to switch pages
 * without react-router (simple state-based routing in App.jsx).
 * `activePage` is 'home' | 'dashboard' — used to highlight the active nav item.
 */
export default function Header({ onDashboard, onHome, activePage = 'home' }) {
  return (
    <header className="app-header">
      <div className="nav-container">
        <div className="brand-block">
          <img
            id="brand-logo"
            src="/static/img/vlookup-logo.png"
            alt="VlookUp Business Solutions"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
          <div className="brand-divider"></div>
          <div className="brand-meta">
            <span className="brand-app-name">Resume Analyzer</span>
            <span className="brand-tagline">Interview Intelligence Studio</span>
          </div>
        </div>

        <nav className="header-nav" aria-label="Main navigation">
          {/* Dashboard button — prominent, matches existing btn-primary style */}
          <button
            className={`btn btn-sm${activePage === 'dashboard' ? ' btn-primary' : ' btn-outline'}`}
            onClick={onDashboard}
            aria-current={activePage === 'dashboard' ? 'page' : undefined}
            title="Open the Interview Dashboard"
          >
            📋 Dashboard
          </button>

          {activePage === 'dashboard' && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={onHome}
              title="Back to resume upload"
            >
              ← Upload
            </button>
          )}
        </nav>

        <div className="header-status-badge">
          <span className="status-dot"></span>
          <span>Talent Evaluation Ready</span>
        </div>
      </div>
    </header>
  );
}
