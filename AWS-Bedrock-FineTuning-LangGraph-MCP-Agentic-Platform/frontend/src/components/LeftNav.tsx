import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { ScenarioSummary } from "../api/types";

interface LeftNavProps {
  selectedScenarioId: string | null;
  learningMlActive: boolean;
  onSelectHome: () => void;
  onSelectScenario: (id: string) => void;
  onSelectLearningMl: () => void;
}

export function LeftNav({
  selectedScenarioId,
  learningMlActive,
  onSelectHome,
  onSelectScenario,
  onSelectLearningMl,
}: LeftNavProps) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);

  useEffect(() => {
    // Only enabled scenarios are ever returned — flipping a YAML flag on the
    // backend is the only way to add or remove an entry here, never a frontend change.
    api.listScenarios().then(setScenarios).catch(console.error);
  }, []);

  return (
    <nav className="left-nav">
      <a
        className={`nav-item ${selectedScenarioId === null && !learningMlActive ? "active" : ""}`}
        onClick={onSelectHome}
      >
        Home
      </a>

      <div className="nav-section-header">Fine-Tuning Demos</div>

      {scenarios.map((scenario) => (
        <a
          key={scenario.id}
          className={`nav-item ${selectedScenarioId === scenario.id ? "active" : ""}`}
          onClick={() => onSelectScenario(scenario.id)}
        >
          <div className="nav-demo-title">{scenario.display_name}</div>
          <div className="nav-demo-tagline">{scenario.tagline}</div>
        </a>
      ))}

      <div className="nav-resources">
        <div className="nav-section-header">Resources</div>
        <a
          className={`nav-item ${learningMlActive ? "active" : ""}`}
          onClick={onSelectLearningMl}
        >
          <div className="nav-demo-title">📘 Learning ML</div>
          <div className="nav-demo-tagline">Definitions, examples, and key concepts</div>
        </a>
      </div>

      <div className="nav-footer">
        Powered by <strong>Amazon Bedrock</strong>
      </div>
    </nav>
  );
}
