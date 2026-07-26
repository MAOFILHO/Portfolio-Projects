export function ContosoLogo() {
  return (
    <div className="brand">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <rect width="13" height="13" x="0" y="0" fill="#0078d4" />
        <rect width="13" height="13" x="15" y="0" fill="#50e6ff" />
        <rect width="13" height="13" x="0" y="15" fill="#83b9f9" />
        <rect width="13" height="13" x="15" y="15" fill="#005ba1" />
      </svg>
      <span className="brand-name">Contoso</span>
    </div>
  );
}
