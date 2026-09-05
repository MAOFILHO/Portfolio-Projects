# All servers front one synthetic backend, not real third-party APIs

Every server queries one Postgres database behind one small HTTP API, run under
Docker Compose and seeded per task. Real services were rejected because auth,
rate limits and drifting data make results irreproducible, and reproducibility
is the point: a reader clones the repo and regenerates the table. The five
reference scenarios all sit inside one company's engineering operations, so a
single backend serves them without strain.
