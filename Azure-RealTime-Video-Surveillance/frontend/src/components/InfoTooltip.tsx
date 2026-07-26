interface InfoTooltipProps {
  text: string;
}

/** Small "(?)" affordance that reveals `text` on hover/focus, keeping
 * secondary explanations out of the page's default reading flow while
 * staying keyboard/screen-reader accessible (native title + focusable button). */
export function InfoTooltip({ text }: InfoTooltipProps) {
  return (
    <span className="info-tooltip" tabIndex={0}>
      <button type="button" className="info-tooltip-trigger" aria-label={text}>
        ?
      </button>
      <span className="info-tooltip-bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}
