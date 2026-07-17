import { useEffect, useState } from "react";
import { LearnContent, learnApi } from "../api/bffClient";

export default function Learn() {
  const [content, setContent] = useState<LearnContent | null>(null);

  useEffect(() => {
    learnApi.content().then(setContent).catch(() => {});
  }, []);

  if (!content) return <p className="muted">Loading…</p>;

  return (
    <div className="grid" style={{ gap: "1.5rem" }}>
      <section className="card">
        <h1>Learn: Why Microservices?</h1>
        <p className="muted">
          Sourced from the Strangler Fig migration study guides used to design this project.
        </p>
      </section>

      <section className="card">
        <h2>Key Advantages</h2>
        <div className="grid cols-2">
          {content.advantages.map((a) => (
            <div key={a.title} className="card">
              <h3>{a.title}</h3>
              <p className="muted">{a.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>The Strangler Fig Pattern — 7 Steps</h2>
        <ol>
          {content.strangler_fig_steps.map((step) => (
            <li key={step} style={{ marginBottom: "0.5rem" }}>
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section className="card">
        <h2>Anti-Patterns to Avoid</h2>
        <h3>Technical</h3>
        <div className="grid cols-2">
          {content.anti_patterns.technical.map((p) => (
            <div key={p.name} className="card">
              <strong>{p.name}</strong>
              <p className="muted">{p.why}</p>
            </div>
          ))}
        </div>
        <h3 style={{ marginTop: "1rem" }}>Organizational</h3>
        <div className="grid cols-2">
          {content.anti_patterns.organizational.map((p) => (
            <div key={p.name} className="card">
              <strong>{p.name}</strong>
              <p className="muted">{p.why}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Glossary</h2>
        <dl>
          {Object.entries(content.glossary).map(([term, def]) => (
            <div key={term} style={{ marginBottom: "0.75rem" }}>
              <dt style={{ fontWeight: 600 }}>{term}</dt>
              <dd className="muted" style={{ marginLeft: 0 }}>
                {def}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card">
        <h2>FAQ</h2>
        {content.faq.map((item) => (
          <div key={item.q} style={{ marginBottom: "1rem" }}>
            <strong>{item.q}</strong>
            <p className="muted">{item.a}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
