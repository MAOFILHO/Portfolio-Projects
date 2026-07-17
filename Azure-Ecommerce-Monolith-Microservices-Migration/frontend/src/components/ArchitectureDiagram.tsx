import { MigrationSnapshot } from "../api/bffClient";

type NodeState = "not-created" | "creating" | "live" | "retiring" | "retired" | "failed";

function stepState(steps: MigrationSnapshot["steps"], id: string): NodeState {
  const step = steps.find((s) => s.id === id);
  if (!step) return "not-created";
  if (step.status === "running") return "creating";
  if (step.status === "done") return "live";
  if (step.status === "failed") return "failed";
  return "not-created";
}

function monolithState(steps: MigrationSnapshot["steps"]): NodeState {
  const step = steps.find((s) => s.id === "decommission");
  if (!step) return "live";
  if (step.status === "running") return "retiring";
  if (step.status === "done") return "retired";
  if (step.status === "failed") return "failed";
  return "live";
}

const STATE_STYLE: Record<NodeState, { border: string; background: string; label: string }> = {
  "not-created": { border: "2px dashed var(--contoso-border)", background: "transparent", label: "not created yet" },
  creating: { border: "2px solid var(--contoso-warning)", background: "#fff3d6", label: "creating…" },
  live: { border: "2px solid var(--contoso-success)", background: "#dff6dd", label: "live" },
  retiring: { border: "2px solid var(--contoso-warning)", background: "#fff3d6", label: "retiring…" },
  retired: { border: "2px dashed var(--contoso-muted)", background: "transparent", label: "decommissioned" },
  failed: { border: "2px solid var(--contoso-danger)", background: "#fde7ea", label: "failed" },
};

function ServiceBox({ name, dbName, state }: { name: string; dbName: string; state: NodeState }) {
  const style = STATE_STYLE[state];
  const faded = state === "not-created" || state === "retired";
  return (
    <div
      style={{
        border: style.border,
        background: style.background,
        borderRadius: 8,
        padding: "0.6rem 0.8rem",
        minWidth: 130,
        textAlign: "center",
        opacity: faded ? 0.55 : 1,
        transition: "all 0.4s ease",
      }}
    >
      <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{name}</div>
      <div className="muted" style={{ fontSize: "0.72rem", marginTop: 2 }}>
        {style.label}
      </div>
      {state !== "not-created" && (
        <div
          style={{
            marginTop: 6,
            fontSize: "0.68rem",
            borderTop: "1px solid var(--contoso-border)",
            paddingTop: 4,
            opacity: faded ? 0.6 : 0.85,
          }}
        >
          DB: {dbName}
        </div>
      )}
    </div>
  );
}

function Arrow({ active }: { active: boolean }) {
  return (
    <div
      style={{
        fontSize: "1.3rem",
        color: active ? "var(--contoso-blue)" : "var(--contoso-border)",
        transition: "color 0.4s ease",
      }}
    >
      →
    </div>
  );
}

export default function ArchitectureDiagram({ snapshot }: { snapshot: MigrationSnapshot }) {
  const monolith = monolithState(snapshot.steps);
  const user = stepState(snapshot.steps, "extract_user");
  const product = stepState(snapshot.steps, "extract_product");
  const order = stepState(snapshot.steps, "extract_order_acl");
  const microservicesActive = snapshot.active_backend === "microservices";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", padding: "0.5rem 0" }}>
      <ServiceBox name="Frontend" dbName="—" state="live" />
      <Arrow active />
      <ServiceBox name="BFF" dbName="—" state="live" />

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", alignItems: "center" }}>
        <Arrow active={!microservicesActive} />
        <span className="muted" style={{ fontSize: "0.68rem" }}>monolith path</span>
      </div>
      <ServiceBox name="Monolith" dbName="monolith_db" state={monolith} />

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", alignItems: "center", marginLeft: "0.5rem" }}>
        <Arrow active={microservicesActive} />
        <span className="muted" style={{ fontSize: "0.68rem" }}>microservices path</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        <ServiceBox name="user-service" dbName="user_db" state={user} />
        <ServiceBox name="product-service" dbName="product_db" state={product} />
        <ServiceBox name="order-service" dbName="order_db" state={order} />
      </div>
    </div>
  );
}
