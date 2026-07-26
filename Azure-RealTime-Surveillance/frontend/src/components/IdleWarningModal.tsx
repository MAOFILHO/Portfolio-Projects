interface IdleWarningModalProps {
  secondsRemaining: number;
  onStayActive: () => void;
}

export function IdleWarningModal({ secondsRemaining, onStayActive }: IdleWarningModalProps) {
  return (
    <div className="modal-backdrop">
      <div className="modal-content idle-warning-content">
        <h3>Still there?</h3>
        <p className="capture-hint">
          You'll be signed out due to inactivity in <strong>{secondsRemaining}s</strong>.
        </p>
        <button onClick={onStayActive}>Stay Signed In</button>
      </div>
    </div>
  );
}
