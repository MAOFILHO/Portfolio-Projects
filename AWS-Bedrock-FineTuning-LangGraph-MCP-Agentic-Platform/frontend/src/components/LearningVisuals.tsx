// SVG diagrams for the Learning ML article, plotted from the sample data in
// assets/references/learning_ml_frontend_pack.md. Sample data, not live
// metrics from any run — each chart says so explicitly.

import type { ReactNode } from "react";

function ChartFrame({
  title,
  caption,
  children,
}: {
  title: string;
  caption: string;
  children: ReactNode;
}) {
  return (
    <div className="learning-chart-card">
      <h5>{title}</h5>
      {children}
      <p className="learning-chart-caption">{caption}</p>
    </div>
  );
}

const LOSS_DATA = [
  { epoch: 1, training_loss: 1.2, validation_loss: 1.25 },
  { epoch: 2, training_loss: 0.98, validation_loss: 1.05 },
  { epoch: 3, training_loss: 0.82, validation_loss: 0.94 },
  { epoch: 4, training_loss: 0.68, validation_loss: 0.88 },
  { epoch: 5, training_loss: 0.56, validation_loss: 0.83 },
  { epoch: 6, training_loss: 0.47, validation_loss: 0.81 },
  { epoch: 7, training_loss: 0.4, validation_loss: 0.8 },
  { epoch: 8, training_loss: 0.34, validation_loss: 0.82 },
  { epoch: 9, training_loss: 0.29, validation_loss: 0.86 },
  { epoch: 10, training_loss: 0.25, validation_loss: 0.92 },
];

function lossToSvgPath(key: "training_loss" | "validation_loss"): string {
  const maxLoss = 1.3;
  const plotX = (epoch: number) => 36 + ((epoch - 1) / 9) * 250;
  const plotY = (loss: number) => 12 + (1 - loss / maxLoss) * 130;
  return LOSS_DATA.map((point, i) => {
    const cmd = i === 0 ? "M" : "L";
    return `${cmd}${plotX(point.epoch).toFixed(1)},${plotY(point[key]).toFixed(1)}`;
  }).join(" ");
}

export function FitCurvesChart() {
  const overfitEpoch = 7;
  const plotX = (epoch: number) => 36 + ((epoch - 1) / 9) * 250;
  return (
    <ChartFrame
      title="Training vs. validation loss curve"
      caption="Sample data — training loss keeps dropping while validation loss turns upward after epoch 7, the classic signature of overfitting."
    >
      <svg viewBox="0 0 300 160" className="chart-svg" role="img" aria-label="Training vs validation loss curve">
        <line x1="36" y1="12" x2="36" y2="142" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <line x1="36" y1="142" x2="286" y2="142" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <line
          x1={plotX(overfitEpoch)}
          y1="12"
          x2={plotX(overfitEpoch)}
          y2="142"
          stroke="#e6a92f"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        <text x={plotX(overfitEpoch)} y="8" textAnchor="middle" fontSize="8" fill="#7a4d00">
          overfitting begins
        </text>
        <path d={lossToSvgPath("training_loss")} fill="none" stroke="var(--contoso-blue-700)" strokeWidth="2.5" />
        <path
          d={lossToSvgPath("validation_loss")}
          fill="none"
          stroke="#e6a92f"
          strokeWidth="2.5"
          strokeDasharray="5 3"
        />
        <text x="161" y="156" textAnchor="middle" fontSize="9" fill="var(--contoso-gray-700)">
          Epoch
        </text>
        <text x="10" y="80" textAnchor="middle" fontSize="9" fill="var(--contoso-gray-700)" transform="rotate(-90 10 80)">
          Loss
        </text>
      </svg>
      <div className="learning-mini-chart-legend">
        <span>
          <i style={{ background: "var(--contoso-blue-700)" }} /> Training loss
        </span>
        <span>
          <i style={{ background: "#e6a92f" }} /> Validation loss
        </span>
      </div>
    </ChartFrame>
  );
}

const FIT_MINI_CURVES: Record<
  "Underfitting" | "Overfitting" | "Ideal fit",
  { trainPath: string; valPath: string }
> = {
  Underfitting: {
    trainPath: "M10,72 L45,64 L80,58 L115,54",
    valPath: "M10,76 L45,68 L80,62 L115,58",
  },
  Overfitting: {
    trainPath: "M10,78 L45,42 L80,20 L115,8",
    valPath: "M10,80 L45,45 L80,38 L115,48",
  },
  "Ideal fit": {
    trainPath: "M10,78 L45,46 L80,24 L115,14",
    valPath: "M10,80 L45,49 L80,27 L115,18",
  },
};

export function FitMiniChart({ variant }: { variant: "Underfitting" | "Overfitting" | "Ideal fit" }) {
  const { trainPath, valPath } = FIT_MINI_CURVES[variant];
  return (
    <div className="fit-mini-chart">
      <svg viewBox="0 0 125 85" role="img" aria-label={`${variant} loss curve`}>
        <line x1="10" y1="6" x2="10" y2="80" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <line x1="10" y1="80" x2="120" y2="80" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <path d={trainPath} fill="none" stroke="var(--contoso-blue-700)" strokeWidth="2.5" />
        <path d={valPath} fill="none" stroke="#e6a92f" strokeWidth="2.5" strokeDasharray="4 3" />
      </svg>
      <div className="learning-mini-chart-legend">
        <span>
          <i style={{ background: "var(--contoso-blue-700)" }} /> Training loss
        </span>
        <span>
          <i style={{ background: "#e6a92f" }} /> Validation loss
        </span>
      </div>
    </div>
  );
}

export function ModelComparisonBarChart() {
  const models = [
    { model: "v1", accuracy: 0.81, f1: 0.78 },
    { model: "v2", accuracy: 0.85, f1: 0.83 },
    { model: "v3", accuracy: 0.88, f1: 0.87 },
  ];
  const plotHeight = 90;
  return (
    <ChartFrame
      title="Model comparison — accuracy and F1"
      caption="Sample data — v3 performs best overall on both metrics and is the strongest candidate for promotion."
    >
      <svg viewBox="0 0 260 130" className="chart-svg" role="img" aria-label="Model comparison bar chart">
        <line x1="30" y1="10" x2="30" y2="110" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <line x1="30" y1="110" x2="250" y2="110" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        {models.map((m, i) => {
          const groupX = 45 + i * 70;
          const accHeight = m.accuracy * plotHeight;
          const f1Height = m.f1 * plotHeight;
          return (
            <g key={m.model}>
              <rect x={groupX} y={110 - accHeight} width="22" height={accHeight} fill="var(--contoso-blue-700)" rx="2" />
              <rect x={groupX + 26} y={110 - f1Height} width="22" height={f1Height} fill="#e6a92f" rx="2" />
              <text x={groupX + 24} y="123" textAnchor="middle" fontSize="9" fill="var(--contoso-gray-700)">
                {m.model}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="learning-mini-chart-legend">
        <span>
          <i style={{ background: "var(--contoso-blue-700)" }} /> Accuracy
        </span>
        <span>
          <i style={{ background: "#e6a92f" }} /> F1 score
        </span>
      </div>
    </ChartFrame>
  );
}

export function ConfusionMatrixDiagram() {
  const labels = ["Billing", "Technical", "Cancellation"];
  const matrix = [
    [48, 2, 1],
    [4, 41, 5],
    [1, 6, 42],
  ];
  return (
    <ChartFrame
      title="Confusion matrix"
      caption="Sample data — most predictions are correct, but Technical and Cancellation tickets are confused in some cases."
    >
      <div className="confusion-matrix-3">
        <div className="cm3-top-label">Predicted class</div>
        <table className="cm3-table">
          <tbody>
            <tr>
              <th className="cm3-side-label" rowSpan={labels.length + 1}>
                Actual class
              </th>
              <th />
              {labels.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
            {matrix.map((row, r) => (
              <tr key={labels[r]}>
                <th className="cm3-row-header">{labels[r]}</th>
                {row.map((value, c) => (
                  <td key={c} className={`cm3-cell ${r === c ? "cm-correct" : "cm-wrong"}`}>
                    {value}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartFrame>
  );
}

export function JobStatusTimelineDiagram() {
  const steps = [
    { time: "4:29 PM", status: "Started" },
    { time: "4:31 PM", status: "Preprocessing" },
    { time: "4:36 PM", status: "Training" },
    { time: "4:42 PM", status: "Evaluating" },
    { time: "4:48 PM", status: "Succeeded" },
  ];
  return (
    <ChartFrame
      title="Job status timeline"
      caption="Sample data — a fine-tuning run moving through setup, training, evaluation, and success."
    >
      <div className="status-timeline">
        {steps.map((step, i) => (
          <div key={step.status} className="status-timeline-step">
            <div className="status-timeline-node">
              <div className="status-timeline-dot" />
              <div className="status-timeline-time">{step.time}</div>
              <div className="status-timeline-label">{step.status}</div>
            </div>
            {i < steps.length - 1 && <div className="status-timeline-line" />}
          </div>
        ))}
      </div>
    </ChartFrame>
  );
}

export function LatencyAccuracyPlot() {
  const points = [
    { label: "A", latency_ms: 45, accuracy: 0.82, color: "var(--contoso-gray-400)" },
    { label: "B", latency_ms: 70, accuracy: 0.86, color: "var(--contoso-blue-700)" },
    { label: "C", latency_ms: 120, accuracy: 0.89, color: "#e6a92f" },
    { label: "D", latency_ms: 35, accuracy: 0.77, color: "var(--contoso-gray-400)" },
    { label: "E", latency_ms: 95, accuracy: 0.88, color: "var(--contoso-blue-700)" },
  ];
  const maxLatency = 140;
  const minAcc = 0.7;
  const maxAcc = 0.92;
  const plotX = (ms: number) => 36 + (ms / maxLatency) * 220;
  const plotY = (acc: number) => 12 + (1 - (acc - minAcc) / (maxAcc - minAcc)) * 90;
  return (
    <ChartFrame
      title="Latency vs. accuracy"
      caption="Sample data — higher accuracy often costs more latency; choose the point that fits the product requirement."
    >
      <svg viewBox="0 0 280 130" className="chart-svg" role="img" aria-label="Latency vs accuracy scatter plot">
        <line x1="36" y1="12" x2="36" y2="102" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <line x1="36" y1="102" x2="266" y2="102" stroke="var(--contoso-gray-400)" strokeWidth="1" />
        <text x="151" y="118" textAnchor="middle" fontSize="9" fill="var(--contoso-gray-700)">
          Latency (ms)
        </text>
        <text x="12" y="55" textAnchor="middle" fontSize="9" fill="var(--contoso-gray-700)" transform="rotate(-90 12 55)">
          Accuracy
        </text>
        {points.map((p) => (
          <g key={p.label}>
            <circle cx={plotX(p.latency_ms)} cy={plotY(p.accuracy)} r="5" fill={p.color} />
            <text x={plotX(p.latency_ms)} y={plotY(p.accuracy) - 10} textAnchor="middle" fontSize="9" fill="var(--contoso-gray-900)">
              {p.label}
            </text>
          </g>
        ))}
      </svg>
    </ChartFrame>
  );
}
