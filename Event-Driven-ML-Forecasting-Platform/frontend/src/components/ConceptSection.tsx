import { CodeBlock } from "./CodeBlock";

interface ConceptSectionProps {
  title: string;
  description: string;
  pytorchCode: string;
  tensorflowCode: string;
  projectNote?: string;
  usedInProject?: boolean;
}

export function ConceptSection({
  title,
  description,
  pytorchCode,
  tensorflowCode,
  projectNote,
  usedInProject = true,
}: ConceptSectionProps) {
  return (
    <section className="concept-section">
      <div className="concept-header">
        <h3>{title}</h3>
        {!usedInProject && <span className="concept-tag general">General reference</span>}
        {usedInProject && <span className="concept-tag used">Used in this project</span>}
      </div>
      <p className="concept-description">{description}</p>
      <div className="code-panels">
        <CodeBlock label="PyTorch" code={pytorchCode} />
        <CodeBlock label="TensorFlow / tf.keras" code={tensorflowCode} />
      </div>
      {projectNote && <div className="project-note">{projectNote}</div>}
    </section>
  );
}
