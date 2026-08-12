export const PHASES = [
  "Foundation model",
  "Dataset",
  "Launch fine-tune",
  "Job status",
  "Inference",
  "Compare",
] as const;

export type Phase = (typeof PHASES)[number];

interface PhaseRailProps {
  currentIndex: number;
}

export function PhaseRail({ currentIndex }: PhaseRailProps) {
  return (
    <div className="phase-rail">
      {PHASES.map((phase, index) => {
        let className = "phase-step";
        if (index === currentIndex) className += " active";
        else if (index < currentIndex) className += " done";
        return (
          <div key={phase} className={className}>
            {index + 1}. {phase}
          </div>
        );
      })}
    </div>
  );
}
