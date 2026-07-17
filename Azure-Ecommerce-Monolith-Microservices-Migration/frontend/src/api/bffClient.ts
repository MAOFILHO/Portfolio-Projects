const BFF_BASE_URL = import.meta.env.VITE_BFF_BASE_URL || "http://127.0.0.1:8000";

export type Backend = "monolith" | "microservices";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BFF_BASE_URL}${path}`, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

function toForm(fields: Record<string, string | number>): URLSearchParams {
  const form = new URLSearchParams();
  for (const [key, value] of Object.entries(fields)) form.append(key, String(value));
  return form;
}

function authHeaders(apiKey: string): HeadersInit {
  return { Authorization: `Basic ${apiKey}` };
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  price: number;
  image: string | null;
}

export interface OrderItem {
  product_id: number;
  quantity: number;
}

export interface Order {
  id?: number;
  user_id?: number;
  is_open: boolean;
  items: OrderItem[];
}

export const shopApi = {
  listProducts: (backend: Backend) => request<{ results: Product[] }>(`/api/shop/${backend}/products`),

  createProduct: (backend: Backend, name: string, slug: string, priceCents: number) =>
    request<{ product: Product }>(`/api/shop/${backend}/product/create`, {
      method: "POST",
      body: toForm({ name, slug, price: priceCents }),
    }),

  register: (backend: Backend, username: string, email: string, password: string) =>
    request<{ result: { username: string } }>(`/api/shop/${backend}/user/create`, {
      method: "POST",
      body: toForm({ username, email, password }),
    }),

  login: (backend: Backend, username: string, password: string) =>
    request<{ api_key: string }>(`/api/shop/${backend}/user/login`, {
      method: "POST",
      body: toForm({ username, password }),
    }),

  addToCart: (backend: Backend, apiKey: string, productId: number, qty: number) =>
    request<{ result: Order }>(`/api/shop/${backend}/order/add-item`, {
      method: "POST",
      headers: authHeaders(apiKey),
      body: toForm({ product_id: productId, qty }),
    }),

  getCart: (backend: Backend, apiKey: string) =>
    request<{ result?: Order; message?: string }>(`/api/shop/${backend}/order`, {
      headers: authHeaders(apiKey),
    }),

  checkout: (backend: Backend, apiKey: string) =>
    request<{ result: Order }>(`/api/shop/${backend}/order/checkout`, {
      method: "POST",
      headers: authHeaders(apiKey),
    }),
};

export interface MigrationStep {
  id: string;
  title: string;
  description: string;
  status: "pending" | "running" | "done" | "failed";
}

export interface MigrationSnapshot {
  mode: "local" | "azure";
  active_backend: Backend;
  running: boolean;
  last_error: string | null;
  steps: MigrationStep[];
}

export const migrationApi = {
  status: () => request<MigrationSnapshot>("/api/migration/status"),
  start: (mode: "local" | "azure") =>
    request<{ message: string }>(`/api/migration/start?mode=${mode}`, { method: "POST" }),
  reset: () => request<MigrationSnapshot>("/api/migration/reset", { method: "POST" }),
  streamUrl: () => `${BFF_BASE_URL}/api/migration/stream`,
};

export interface LearnContent {
  advantages: { title: string; body: string }[];
  strangler_fig_steps: string[];
  anti_patterns: {
    technical: { name: string; why: string }[];
    organizational: { name: string; why: string }[];
  };
  glossary: Record<string, string>;
  faq: { q: string; a: string }[];
}

export const learnApi = {
  content: () => request<LearnContent>("/api/learn/content"),
};

export interface BenchmarkOperationResult {
  operation: string;
  requests: number;
  p50_ms: number;
  p95_ms: number;
  throughput_rps: number;
  errors: number;
}

export interface BenchmarkResult {
  generated_at: string;
  measured: Backend[];
  monolith: BenchmarkOperationResult[];
  microservices: BenchmarkOperationResult[];
}

export const metricsApi = {
  latest: () => request<BenchmarkResult>("/api/metrics/latest"),
  run: () => request<BenchmarkResult>("/api/metrics/run", { method: "POST" }),
};
