import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="grid" style={{ gap: "1.5rem" }}>
      <section className="card">
        <h1>From Monolith to Microservices — live.</h1>
        <p className="muted">
          This project runs the exact same e-commerce application two ways: as a single Flask
          monolith (one process, one database) and as three independently deployable microservices
          (user, product, order — each with its own database). Watch the real strangler-fig
          migration happen, compare real before/after performance metrics, and learn the
          architectural patterns behind it.
        </p>
      </section>

      <div className="grid cols-3">
        <Link to="/shop" className="card" style={{ textDecoration: "none", color: "inherit" }}>
          <h3>Shop</h3>
          <p className="muted">Try the working e-commerce demo against either backend.</p>
        </Link>
        <Link to="/migrate" className="card" style={{ textDecoration: "none", color: "inherit" }}>
          <h3>Migrate</h3>
          <p className="muted">Trigger the live strangler-fig cutover, step by step, in real time.</p>
        </Link>
        <Link to="/learn" className="card" style={{ textDecoration: "none", color: "inherit" }}>
          <h3>Learn</h3>
          <p className="muted">Key advantages, anti-patterns, and the Strangler Fig pattern explained.</p>
        </Link>
      </div>

      <section className="card">
        <h2>Architecture — Before</h2>
        <pre style={{ overflowX: "auto" }}>{`
Browser → BFF → [ Monolith Flask App ]
                    ├── auth blueprint
                    ├── catalog blueprint
                    ├── orders blueprint
                    └── one shared database (Shared Persistence)
`}</pre>
      </section>

      <section className="card">
        <h2>Architecture — After</h2>
        <pre style={{ overflowX: "auto" }}>{`
Browser → BFF (proxy) ──┬──► user-service    → user_db
                        ├──► product-service → product_db
                        └──► order-service   → order_db
                                │
                                └──HTTP──► user-service (Anti-Corruption Layer)
`}</pre>
      </section>
    </div>
  );
}
