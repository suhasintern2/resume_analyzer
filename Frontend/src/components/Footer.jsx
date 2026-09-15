function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-container">
        <div className="footer-top-row">
          <div className="footer-brand">
            <img
              src="/static/img/vlookup-logo.png"
              alt="VlookUp Business Solutions"
              className="footer-logo"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
            <span className="footer-brand-divider"></span>
            <p className="footer-tagline">Helping business change gears</p>
          </div>
          <div className="footer-copyright">
            <p>&copy; 2026 VlookUp Business Solutions Pvt Ltd. All rights reserved.</p>
          </div>
        </div>

        <div className="footer-divider"></div>

        <div className="footer-disclaimer-row">
          <p className="confidential-tag">
            <strong className="disclaimer-badge">DISCLAIMER:</strong>
            This communication is confidential and may be legally privileged. If you are not the
            intended recipient, (i) please do not read or disclose to others, (ii) please notify the
            sender by reply, and (iii) please delete this communication from your system. Failure to
            follow this process may be unlawful.
          </p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;