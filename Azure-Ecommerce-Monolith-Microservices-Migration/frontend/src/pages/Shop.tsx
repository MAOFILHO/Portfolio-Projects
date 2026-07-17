import { FormEvent, useEffect, useState } from "react";
import { Backend, MigrationSnapshot, Order, Product, migrationApi, shopApi } from "../api/bffClient";

interface Auth {
  username: string;
  apiKey: string;
}

function loadAuth(backend: Backend): Auth | null {
  const raw = localStorage.getItem(`shop_auth_${backend}`);
  return raw ? (JSON.parse(raw) as Auth) : null;
}

function saveAuth(backend: Backend, auth: Auth | null) {
  if (auth) localStorage.setItem(`shop_auth_${backend}`, JSON.stringify(auth));
  else localStorage.removeItem(`shop_auth_${backend}`);
}

export default function Shop() {
  const [backend, setBackend] = useState<Backend>("monolith");
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [auth, setAuth] = useState<Auth | null>(() => loadAuth("monolith"));
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  const [cart, setCart] = useState<Order | null>(null);
  const [cartError, setCartError] = useState<string | null>(null);
  const [checkoutMessage, setCheckoutMessage] = useState<string | null>(null);

  const [seedStatus, setSeedStatus] = useState<string | null>(null);

  const [migration, setMigration] = useState<MigrationSnapshot | null>(null);
  const [migrationLoaded, setMigrationLoaded] = useState(false);
  const [restartBusy, setRestartBusy] = useState(false);
  const monolithDecommissioned =
    migration?.steps.find((s) => s.id === "decommission")?.status === "done";
  const isCloud = migration?.mode === "azure";

  useEffect(() => {
    let cancelled = false;
    function poll() {
      migrationApi
        .status()
        .then((data) => {
          if (cancelled) return;
          setMigration(data);
          setMigrationLoaded(true);
        })
        .catch(() => !cancelled && setMigrationLoaded(true));
    }
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  // In the cloud deployment there is only ever one live backend at a time —
  // no side-by-side toggle like local mode's "run-all" convenience — so Shop
  // just follows whatever the migration says is currently active.
  useEffect(() => {
    if (isCloud && migration && migration.active_backend !== backend) {
      setBackend(migration.active_backend);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCloud, migration?.active_backend]);

  async function restartMonolith() {
    // migrationApi.reset() brings the monolith back up (if a prior run
    // decommissioned it) and resets migration step state — there's no
    // separate "just restart the monolith" action, since one never
    // actually existed as distinct backend behavior (see routers/migration.py).
    setRestartBusy(true);
    try {
      const data = await migrationApi.reset();
      setMigration(data);
      if (backend === "monolith") refreshProducts("monolith");
    } finally {
      setRestartBusy(false);
    }
  }

  async function refreshProducts(targetBackend: Backend, attempt = 1) {
    if (attempt === 1) {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await shopApi.listProducts(targetBackend);
      setProducts(data.results);
      setLoading(false);
    } catch (err) {
      // Azure Container Apps on the Consumption plan scale to zero when
      // idle — a cold start can occasionally reset the connection instead
      // of just being slow, surfacing as a generic "Failed to fetch" on the
      // very first request after idle time. Retry a couple of times before
      // showing the user an error, rather than making a transient wake-up
      // blip look like a real outage.
      if (attempt < 3) {
        await new Promise((resolve) => setTimeout(resolve, 2000 * attempt));
        return refreshProducts(targetBackend, attempt + 1);
      }
      setError(String(err));
      setLoading(false);
    }
  }

  function refreshCart(targetBackend: Backend, currentAuth: Auth | null) {
    if (!currentAuth) {
      setCart(null);
      return;
    }
    shopApi
      .getCart(targetBackend, currentAuth.apiKey)
      .then((data) => setCart(data.result ?? null))
      .catch(() => setCart(null));
  }

  useEffect(() => {
    // In cloud mode `backend` starts at its "monolith" default before the
    // first migration-status poll resolves — fetching immediately would
    // fire a doomed request once the monolith's actually been decommissioned
    // (caught for real: this produced a confusing "Could not reach
    // microservices" banner whose body was actually the stale monolith
    // 503, because `backend` had already flipped to "microservices" by the
    // time the error was set). Wait until `backend` agrees with what the
    // migration engine says is actually live before fetching.
    if (!migrationLoaded) return;
    if (isCloud && migration && migration.active_backend !== backend) return;
    const savedAuth = loadAuth(backend);
    setAuth(savedAuth);
    setCheckoutMessage(null);
    refreshProducts(backend);
    refreshCart(backend, savedAuth);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backend, migrationLoaded, isCloud, migration?.active_backend]);

  async function handleAuthSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setAuthError(null);
    setAuthBusy(true);
    const form = new FormData(e.currentTarget);
    const username = String(form.get("username") || "");
    const password = String(form.get("password") || "");
    const email = String(form.get("email") || "");

    try {
      if (authMode === "register") {
        await shopApi.register(backend, username, email, password);
      }
      const { api_key } = await shopApi.login(backend, username, password);
      const newAuth = { username, apiKey: api_key };
      setAuth(newAuth);
      saveAuth(backend, newAuth);
      refreshCart(backend, newAuth);
    } catch (err) {
      setAuthError(String(err));
    } finally {
      setAuthBusy(false);
    }
  }

  function logout() {
    setAuth(null);
    saveAuth(backend, null);
    setCart(null);
  }

  async function addToCart(productId: number) {
    if (!auth) return;
    setCartError(null);
    try {
      const { result } = await shopApi.addToCart(backend, auth.apiKey, productId, 1);
      setCart(result);
    } catch (err) {
      setCartError(String(err));
    }
  }

  async function checkout() {
    if (!auth) return;
    setCartError(null);
    setCheckoutMessage(null);
    try {
      const { result } = await shopApi.checkout(backend, auth.apiKey);
      setCart(result);
      setCheckoutMessage("Order placed! Thank you.");
    } catch (err) {
      setCartError(String(err));
    }
  }

  async function seedSampleProducts() {
    setSeedStatus("Adding sample products…");
    const samples: [string, string, number][] = [
      ["Contoso Mug", "contoso-mug", 1299],
      ["Contoso T-Shirt", "contoso-tshirt", 2499],
      ["Contoso Notebook", "contoso-notebook", 899],
    ];
    try {
      for (const [name, slug, price] of samples) {
        await shopApi.createProduct(backend, name, slug, price);
      }
      setSeedStatus(null);
      refreshProducts(backend);
    } catch (err) {
      setSeedStatus(`Could not add sample products: ${err}`);
    }
  }

  const cartQtyByProduct = new Map((cart?.items ?? []).map((i) => [i.product_id, i.quantity]));
  const cartTotalCents = (cart?.items ?? []).reduce((sum, item) => {
    const product = products.find((p) => p.id === item.product_id);
    return sum + (product?.price ?? 0) * item.quantity;
  }, 0);

  return (
    <div className="grid" style={{ gap: "1.5rem" }}>
      <section className="card">
        <h1>Shop</h1>
        <p className="muted">
          The same catalog, same auth, same cart/checkout flow, served by whichever backend is
          currently live — both run the identical API contract.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", alignItems: "center" }}>
          {isCloud ? (
            <span className="pill done">
              Serving from: {backend === "monolith" ? "Monolith" : "Microservices"} (Azure)
            </span>
          ) : (
            <>
              <button
                className={backend === "monolith" ? "btn" : "btn secondary"}
                disabled={monolithDecommissioned}
                title={monolithDecommissioned ? "The migration decommissioned the monolith process." : undefined}
                onClick={() => setBackend("monolith")}
              >
                Monolith
              </button>
              <button className={backend === "microservices" ? "btn" : "btn secondary"} onClick={() => setBackend("microservices")}>
                Microservices
              </button>
              {monolithDecommissioned && (
                <span className="muted" style={{ fontSize: "0.85rem" }}>
                  Decommissioned by the migration —{" "}
                  <button
                    className="btn secondary"
                    style={{ padding: "0.15rem 0.5rem", fontSize: "0.85rem" }}
                    disabled={restartBusy}
                    onClick={restartMonolith}
                  >
                    {restartBusy ? "Restarting…" : "Restart monolith"}
                  </button>
                </span>
              )}
            </>
          )}
        </div>
      </section>

      <section className="card">
        {auth ? (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>
              Signed in as <strong>{auth.username}</strong> ({backend})
            </span>
            <button className="btn secondary" onClick={logout}>
              Log out
            </button>
          </div>
        ) : (
          <>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <button className={authMode === "register" ? "btn" : "btn secondary"} onClick={() => setAuthMode("register")}>
                Register
              </button>
              <button className={authMode === "login" ? "btn" : "btn secondary"} onClick={() => setAuthMode("login")}>
                Log in
              </button>
            </div>
            <form onSubmit={handleAuthSubmit} style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <input name="username" placeholder="Username" required style={{ padding: "0.5rem" }} />
              {authMode === "register" && (
                <input name="email" type="email" placeholder="Email" required style={{ padding: "0.5rem" }} />
              )}
              <input name="password" type="password" placeholder="Password" required style={{ padding: "0.5rem" }} />
              <button className="btn" type="submit" disabled={authBusy}>
                {authMode === "register" ? "Create account & log in" : "Log in"}
              </button>
            </form>
            {authError && <p style={{ color: "var(--contoso-danger)" }}>{authError}</p>}
          </>
        )}
      </section>

      {loading && <p className="muted">Loading products from {backend}…</p>}
      {error && backend === "monolith" && monolithDecommissioned && (
        <div className="card" style={{ borderColor: "var(--contoso-danger)" }}>
          <strong>The monolith was decommissioned.</strong>
          <p className="muted">
            The last migration run stopped the monolith process as its final step — that's expected,
            not a bug. Switch to Microservices, or restart the monolith using the button above to
            try it again.
          </p>
        </div>
      )}
      {error && !(backend === "monolith" && monolithDecommissioned) && (
        <div className="card" style={{ borderColor: "var(--contoso-danger)" }}>
          <strong>Could not reach {backend}.</strong>
          <p className="muted">{error}</p>
          <p className="muted">
            {backend === "microservices"
              ? "If the microservices haven't been started yet, go to the Migrate page and run the migration first."
              : "Make sure `make run` is running the monolith service."}
          </p>
        </div>
      )}

      {!loading && !error && (
        <section className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>Products</h2>
            {products.length === 0 && (
              <button className="btn secondary" onClick={seedSampleProducts}>
                Add sample products
              </button>
            )}
          </div>
          {seedStatus && <p className="muted">{seedStatus}</p>}
          <div className="grid cols-3">
            {products.length === 0 && !seedStatus && <p className="muted">No products yet.</p>}
            {products.map((p) => (
              <div key={p.id} className="card">
                <h3>{p.name}</h3>
                <p className="muted">${(p.price / 100).toFixed(2)}</p>
                {cartQtyByProduct.has(p.id) && (
                  <p className="pill done" style={{ marginBottom: "0.5rem" }}>
                    {cartQtyByProduct.get(p.id)} in cart
                  </p>
                )}
                <button className="btn" disabled={!auth} onClick={() => addToCart(p.id)}>
                  {auth ? "Add to cart" : "Log in to buy"}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {auth && (
        <section className="card">
          <h2>Cart</h2>
          {cartError && <p style={{ color: "var(--contoso-danger)" }}>{cartError}</p>}
          {checkoutMessage && <p style={{ color: "var(--contoso-success)" }}>{checkoutMessage}</p>}
          {!cart || cart.items.length === 0 ? (
            <p className="muted">Your cart is empty.</p>
          ) : (
            <>
              <ul className="timeline">
                {cart.items.map((item) => {
                  const product = products.find((p) => p.id === item.product_id);
                  const lineTotalCents = (product?.price ?? 0) * item.quantity;
                  return (
                    <li key={item.product_id}>
                      <span>
                        {product?.name ?? `Product #${item.product_id}`}
                        <span className="muted"> × {item.quantity}</span>
                      </span>
                      <span>${(lineTotalCents / 100).toFixed(2)}</span>
                    </li>
                  );
                })}
              </ul>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "1rem", fontSize: "1.1rem" }}>
                <strong>Total</strong>
                <strong>${(cartTotalCents / 100).toFixed(2)}</strong>
              </div>
              <button className="btn" style={{ marginTop: "1rem" }} disabled={!cart.is_open} onClick={checkout}>
                {cart.is_open ? `Checkout — $${(cartTotalCents / 100).toFixed(2)}` : "Order placed"}
              </button>
            </>
          )}
        </section>
      )}
    </div>
  );
}
