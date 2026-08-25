/** Same-origin API (FastAPI serves SPA + JSON under one origin). */
export const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "";

export type StatsResponse = {
  total_agents: number;
  free_tier_active: number;
  pro_tier_active: number;
  tool_credits_sold: number;
  revenue_today_usd: number;
  calls_today: number;
  avg_latency_ms: number;
  active_tools: string[];
  free_tools: string[];
  paid_tools: string[];
  tool_count: number;
  pricing: Record<string, string>;
  network: string;
  pay_to_configured: boolean;
  timestamp: string;
};

export type DoctorCheck = {
  id: string;
  name: string;
  status: "pass" | "fail" | "warn" | "skip";
  message: string;
  fix?: string;
};

export type DoctorResponse = {
  status: string;
  timestamp: string;
  checks: DoctorCheck[];
};

export type HealthResponse = {
  status: string;
  service?: string;
  version?: string;
  timestamp?: string;
  components?: Record<string, unknown>;
};

export type WalletResponse = {
  seller_receive_address: string | null;
  seller_receive_address_full?: string | null;
  buyer_address: string;
  network: string;
  pay_to_configured: boolean;
};

async function getJson<T>(path: string): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${path} → ${res.status}${text ? `: ${text.slice(0, 200)}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => getJson<HealthResponse>("/health"),
  stats: () => getJson<StatsResponse>("/stats"),
  doctor: () => getJson<DoctorResponse>("/doctor"),
  wallet: () => getJson<WalletResponse>("/wallet"),
  fetchPrice: async (symbol: string) => {
    const q = new URLSearchParams({ symbol });
    const res = await fetch(`${API_BASE}/tools/fetch_price?${q}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body?.detail || `fetch_price failed: ${res.status}`);
    return body;
  },
};
