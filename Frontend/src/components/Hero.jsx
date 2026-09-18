function Hero({ hidden }) {
  return (
    <section className={hidden ? 'hero-banner hidden' : 'hero-banner'} id="hero-banner">
      <div className="hero-content">
        <span className="hero-pill">Candidate assesment </span>
        <p className="hero-subtitle">
          Upload or scan any developer resume to instantly extract technical depth, generate
          contextual questions across 5 core dimensions, and review recommended talking points.
        </p>
      </div>
    </section>
  );
}

export default Hero;