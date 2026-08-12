import {
  ConfusionMatrixDiagram,
  FitCurvesChart,
  FitMiniChart,
  JobStatusTimelineDiagram,
  LatencyAccuracyPlot,
  ModelComparisonBarChart,
} from "../components/LearningVisuals";

interface Topic {
  id: string;
  title: string;
  whatItIs: string;
  whatItDoes: string;
  whenToUse: string;
  example: string;
}

const TOPICS: Topic[] = [
  {
    id: "foundation-model",
    title: "1. Foundation model",
    whatItIs: "A large, pre-trained model that already understands broad patterns from massive amounts of data.",
    whatItDoes: "It gives you a strong starting point, so you do not need to train a model from scratch.",
    whenToUse: "Use it when you want faster time to value, less training data, and better baseline performance.",
    example: "A language model that can summarize text, answer questions, and classify messages after light adaptation.",
  },
  {
    id: "dataset",
    title: "2. Dataset",
    whatItIs: "The labeled or unlabeled information used to adapt and evaluate the model.",
    whatItDoes: "It teaches the model your domain, your labels, and your business rules.",
    whenToUse: "Use a high-quality dataset when accuracy matters and your use case is specific.",
    example: "Customer support tickets labeled as billing, technical issue, or cancellation.",
  },
  {
    id: "launch-fine-tune",
    title: "3. Launch fine-tune",
    whatItIs: "Fine-tuning updates a foundation model using your dataset so it performs better on your task.",
    whatItDoes: "It adapts the model to your language, categories, policies, or visual patterns.",
    whenToUse: "Use it when the base model is close, but not good enough for your production target.",
    example: "Fine-tuning a classifier to detect internal support categories.",
  },
  {
    id: "job-status",
    title: "4. Job status",
    whatItIs: "Job status shows the state of the training or fine-tuning run.",
    whatItDoes: "It tells users whether the job is queued, running, completed, failed, or stopped.",
    whenToUse: "Use it for monitoring progress, troubleshooting failures, and estimating completion time.",
    example: "A training job running for 28 minutes with logs updating every few seconds.",
  },
  {
    id: "inference",
    title: "5. Inference",
    whatItIs: "Inference is the act of using the trained model to make a prediction on new input.",
    whatItDoes: "It returns a label, score, probability, or generated response.",
    whenToUse: "Use it whenever the application needs a live prediction from the trained model.",
    example: "Classifying a new email as urgent or non-urgent.",
  },
  {
    id: "compare",
    title: "6. Compare",
    whatItIs: "Compare lets users evaluate runs, models, or datasets side by side.",
    whatItDoes: "It helps identify the best model based on metrics, cost, latency, and quality.",
    whenToUse: "Use it before promoting a model to production.",
    example: "Comparing version A and version B on accuracy, recall, and latency.",
  },
];

const KEY_CONCEPTS: { concept: string; meaning: string }[] = [
  { concept: "Overfitting", meaning: "Great on training data, weak on new data." },
  { concept: "Underfitting", meaning: "Too simple to learn the pattern well." },
  { concept: "Ideal fit", meaning: "Strong training and validation performance with small gap." },
  { concept: "Accuracy", meaning: "Percent of correct predictions." },
  { concept: "Precision", meaning: "How many positive predictions were correct." },
  { concept: "Recall", meaning: "How many real positives were found." },
  { concept: "Loss", meaning: "How wrong the model is during training." },
];

const FIT_DETAILS: {
  name: "Underfitting" | "Overfitting" | "Ideal fit";
  performance: string;
  causes: string[];
  fixes: string[];
}[] = [
  {
    name: "Underfitting",
    performance: "High training loss and high validation loss — the model is inaccurate on data it has already seen.",
    causes: ["Model too small", "Too few training steps", "Weak features", "Poor learning rate setup"],
    fixes: ["Train longer", "Use a larger model", "Improve features", "Tune learning rate", "Increase capacity"],
  },
  {
    name: "Overfitting",
    performance: "Very low training loss, but rising validation loss — great on training data, weak on new data.",
    causes: [
      "Too many parameters for the data size",
      "Not enough data",
      "Too many training epochs",
      "Noisy or duplicated labels",
    ],
    fixes: ["Use more data", "Add regularization", "Early stopping", "Simplify the model", "Improve label quality"],
  },
  {
    name: "Ideal fit",
    performance: "Low training loss and low validation loss with a small, stable gap between them.",
    causes: ["Balanced model capacity", "Good data quality", "Proper regularization"],
    fixes: ["Keep the current setup", "Validate on fresh data", "Monitor drift after launch"],
  },
];

const METRICS: { metric: string; definition: string; bestWhen: string }[] = [
  { metric: "Accuracy", definition: "Overall percent of correct predictions.", bestWhen: "Classes are balanced and all mistakes matter similarly." },
  { metric: "Precision", definition: "How many predicted positives were correct.", bestWhen: "False positives are expensive." },
  { metric: "Recall", definition: "How many real positives were found.", bestWhen: "False negatives are expensive." },
  { metric: "F1 score", definition: "Balance between precision and recall.", bestWhen: "You need one score that balances both." },
  { metric: "Loss", definition: "How far predictions are from the target.", bestWhen: "Tracking training progress and model fitting." },
  { metric: "Latency", definition: "Time to produce a prediction.", bestWhen: "Real-time applications." },
];

export function LearningMLPage() {
  return (
    <div className="learning-ml">
      <nav className="learning-toc">
        {TOPICS.map((topic) => (
          <a key={topic.id} href={`#${topic.id}`} className="learning-toc-link">
            {topic.title.replace(/^\d+\.\s/, "")}
          </a>
        ))}
        <a href="#key-concepts" className="learning-toc-link">
          Key concepts
        </a>
        <a href="#fit-quality" className="learning-toc-link">
          Overfit / underfit
        </a>
        <a href="#metrics" className="learning-toc-link">
          Metrics
        </a>
        <a href="#reading-quality" className="learning-toc-link">
          Reading quality
        </a>
      </nav>

      <h2>Learning ML</h2>
      <p className="learning-intro">
        A practical guide to foundation models, datasets, fine-tuning, job status, inference, and
        comparison — written for product users and technical teams. Each step below mirrors a
        phase of the demo on the left, so you can read the concept here and then click through the
        real thing.
      </p>

      {TOPICS.map((topic) => (
        <section key={topic.id} id={topic.id} className="learning-section">
          <h3>{topic.title}</h3>
          <div className="learning-callout-grid">
            <div className="learning-callout">
              <div className="learning-callout-label">What it is</div>
              <div>{topic.whatItIs}</div>
            </div>
            <div className="learning-callout">
              <div className="learning-callout-label">What it does</div>
              <div>{topic.whatItDoes}</div>
            </div>
            <div className="learning-callout">
              <div className="learning-callout-label">When to use it</div>
              <div>{topic.whenToUse}</div>
            </div>
            <div className="learning-callout">
              <div className="learning-callout-label">Example</div>
              <div>{topic.example}</div>
            </div>
          </div>
          {topic.id === "job-status" && <JobStatusTimelineDiagram />}
          {topic.id === "compare" && <ModelComparisonBarChart />}
        </section>
      ))}

      <section id="key-concepts" className="learning-section">
        <h3>Key concepts</h3>
        <p>
          These terms come up constantly once a model is training or being evaluated. Skim the
          table now — the sections below unpack the fit-related ones (overfitting, underfitting,
          ideal fit) in more depth.
        </p>
        <table className="concept-table">
          <thead>
            <tr>
              <th>Concept</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            {KEY_CONCEPTS.map((row) => (
              <tr key={row.concept}>
                <td>
                  <strong>{row.concept}</strong>
                </td>
                <td>{row.meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section id="fit-quality" className="learning-section">
        <h3>Overfitting, underfitting, and ideal fit</h3>
        <p>
          The relationship between training loss and validation loss over the course of training
          is the single clearest signal for how well a model is actually learning. The chart below
          shows the shape of each pattern.
        </p>
        <FitCurvesChart />
        <div className="fit-detail-grid">
          {FIT_DETAILS.map((fit) => (
            <div key={fit.name} className="fit-detail-card">
              <h4>{fit.name}</h4>
              <div className="fit-detail-row">
                <span className="fit-detail-label">Performance</span>
                <span>{fit.performance}</span>
              </div>
              <div className="fit-detail-row">
                <span className="fit-detail-label">Causes</span>
                <ul className="fit-detail-list">
                  {fit.causes.map((cause) => (
                    <li key={cause}>{cause}</li>
                  ))}
                </ul>
              </div>
              <div className="fit-detail-row">
                <span className="fit-detail-label">How to fix it</span>
                <ul className="fit-detail-list">
                  {fit.fixes.map((fix) => (
                    <li key={fix}>{fix}</li>
                  ))}
                </ul>
              </div>
              <FitMiniChart variant={fit.name} />
            </div>
          ))}
        </div>
        <ConfusionMatrixDiagram />
      </section>

      <section id="metrics" className="learning-section">
        <h3>Metrics — which one to trust, and when</h3>
        <p>
          No single number tells the whole story. Use this table to pick the metric that matches
          what actually matters for your use case.
        </p>
        <table className="concept-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Definition</th>
              <th>Best when</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map((row) => (
              <tr key={row.metric}>
                <td>
                  <strong>{row.metric}</strong>
                </td>
                <td>{row.definition}</td>
                <td>{row.bestWhen}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section id="reading-quality" className="learning-section">
        <h3>How to read model quality</h3>
        <ul className="learning-list">
          <li>
            <strong>High accuracy is useful, but it is not enough by itself.</strong> A model can
            be accurate overall and still miss an important class — for example, a fraud detector
            that is 99% accurate but misses most real fraud cases because fraud is rare in the
            data.
          </li>
          <li>
            <strong>Low accuracy usually means the model needs better data, better labels, a
            better base model, or more tuning</strong> — not necessarily a fundamentally different
            approach.
          </li>
          <li>
            <strong>Look at accuracy together with precision, recall, F1 score, validation loss,
            and inference latency.</strong> Any single metric can look good while the model is
            still wrong in ways that matter for your use case.
          </li>
        </ul>
        <LatencyAccuracyPlot />
      </section>
    </div>
  );
}
