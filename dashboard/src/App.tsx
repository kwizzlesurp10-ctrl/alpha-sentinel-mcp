import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type DoctorResponse,
  type HealthResponse,
  type StatsResponse,
  type WalletResponse,
} from "./api";

type LoadState = "idle" | "loading" | "ready" | "error";

function statusPill(health?: HealthResponse | null, error?: string | null) {
  if (error) return { cls: "err", label: "API unreachable" };
  if (!health) return { cls: "", label: "Connecting…" };
  if (health.status === "healthy") return { cls: "ok", label: "System operational" };
  return { cls: "warn", label: health.status || "Degraded" };
}

function CheckIcon({ status }: { status: string }) {
  const cls =
    status === "pass" ? "status-pass" : status === "warn" ? "status-warn" : "status-fail";
  const glyph = status === "pass" ? "●" : status === "warn" ? "▲" : "■";
  return <span className={cls}>{glyph}</span>;
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [doctor, setDoctor] = useState<DoctorResponse | null>(null);
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  const [symbol, setSymbol] = useState("btc");
  const [toolBusy, setToolBusy] = useState(false);
  const [toolOut, setToolOut] = useState<string>("// Try fetch_price — free tier friendly");
  const [toolErr, setToolErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [h, s, d, w] = await Promise.all([
        api.health(),
        api.stats(),
        api.doctor(),
        api.wallet(),
      ]);
      setHealth(h);
      setStats(s);
      setDoctor(d);
      setWallet(w);
      setState("ready");
    } catch (e) {
      setState("error");
      setError(e instanceof Error ? e.message : "Failed to load Mission Control data");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  const pill = useMemo(() => statusPill(health, error), [health, error]);

  const runPrice = async () => {
    setToolBusy(true);
    setToolErr(null);
    setToolOut("Fetching…");
    try {
      const data = await api.fetchPrice(symbol.trim() || "btc");
      setToolOut(JSON.stringify(data, null, 2));
      // Soft refresh stats after a free call
      api.stats().then(setStats).catch(() => undefined);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Tool call failed";
      setToolErr(msg);
      setToolOut(`// error\n${msg}`);
    } finally {
      setToolBusy(false);
    }
  };

  const tools = stats?.active_tools ?? [];
  const free = new Set(stats?.free_tools ?? ["fetch_price"]);
  const pricing = stats?.pricing ?? {};

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            🛡
          </div>
          <div>
            <h1>Alpha Sentinel</h1>
            <div className="tagline">Mission Control · Market Intelligence x402</div>
          </div>
        </div>
        <div className="header-actions">
          <div className={`pill ${pill.cls}`}>
            <span className="dot" />
            <span>{pill.label}</span>
          </div>
          {stats?.network && (
            <div className="pill hide-mobile mono">{stats.network}</div>
          )}
          <button className="btn" type="button" onClick={refresh}>
            Refresh
          </button>
          <a className="btn btn-primary" href="/api/docs" target="_blank" rel="noreferrer">
            API Docs
          </a>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <strong>Live API error:</strong> {error}
          <div className="muted" style={{ marginTop: 6 }}>
            If this is a fresh deploy, wait ~30s for the Python function cold start, then retry.
          </div>
        </div>
      )}

      <section className="grid stats" style={{ marginBottom: 14 }}>
        <div className="card stat-card">
          <div className="card-title">Calls today</div>
          {state === "loading" && !stats ? (
            <div className="skeleton" />
          ) : (
            <>
              <div className="stat-value">{stats?.calls_today ?? "—"}</div>
              <div className="stat-sub">avg {stats?.avg_latency_ms ?? 0} ms</div>
            </>
          )}
        </div>
        <div className="card stat-card green">
          <div className="card-title">Free agents</div>
          <div className="stat-value">{stats?.free_tier_active ?? "—"}</div>
          <div className="stat-sub">{stats?.total_agents ?? 0} total agents</div>
        </div>
        <div className="card stat-card amber">
          <div className="card-title">Pro agents</div>
          <div className="stat-value">{stats?.pro_tier_active ?? "—"}</div>
          <div className="stat-sub">credits sold {stats?.tool_credits_sold ?? 0}</div>
        </div>
        <div className="card stat-card violet">
          <div className="card-title">Revenue (today)</div>
          <div className="stat-value mono">
            ${(stats?.revenue_today_usd ?? 0).toFixed(2)}
          </div>
          <div className="stat-sub">{stats?.tool_count ?? tools.length} tools live</div>
        </div>
      </section>

      <section className="grid main">
        <div className="grid" style={{ gap: 14 }}>
          <div className="card">
            <div className="card-title">
              <span>Try tool · fetch_price</span>
              <span className="chip chip-free">FREE</span>
            </div>
            <div className="form-row">
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="btc / eth / sol"
                aria-label="Symbol"
              />
              <button
                className="btn btn-primary"
                type="button"
                disabled={toolBusy}
                onClick={runPrice}
              >
                {toolBusy ? "Running…" : "Run"}
              </button>
            </div>
            {toolErr && <div className="error-banner">{toolErr}</div>}
            <pre className="output">{toolOut}</pre>
          </div>

          <div className="card">
            <div className="card-title">Active tools & pricing</div>
            {tools.length === 0 ? (
              <p className="muted">No tools reported yet — check /stats after API is up.</p>
            ) : (
              <ul className="tools-list">
                {tools.map((name) => (
                  <li key={name} className="tool-row">
                    <span className="tool-name">{name}</span>
                    <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span className="mono muted">{pricing[name] ?? "—"}</span>
                      <span className={`chip ${free.has(name) ? "chip-free" : "chip-paid"}`}>
                        {free.has(name) ? "FREE" : "PAID"}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="grid" style={{ gap: 14 }}>
          <div className="card">
            <div className="card-title">
              <span>Doctor</span>
              <span className="mono muted">{doctor?.status ?? "—"}</span>
            </div>
            {!doctor ? (
              <div className="skeleton" style={{ height: 80 }} />
            ) : (
              <div className="check-list">
                {doctor.checks.map((c) => (
                  <div key={c.id} className="check-row">
                    <CheckIcon status={c.status} />
                    <div>
                      <div className="name">{c.name}</div>
                      <div className="msg">{c.message}</div>
                      {c.fix && c.status !== "pass" && <div className="fix">{c.fix}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-title">Wallet & settlement</div>
            <div className="check-list">
              <div className="check-row">
                <span className="status-pass">◆</span>
                <div>
                  <div className="name">Seller receive</div>
                  <div className="msg mono">
                    {wallet?.seller_receive_address_full ||
                      wallet?.seller_receive_address ||
                      "not configured"}
                  </div>
                </div>
              </div>
              <div className="check-row">
                <span className={wallet?.pay_to_configured ? "status-pass" : "status-fail"}>
                  ◆
                </span>
                <div>
                  <div className="name">Pay-to configured</div>
                  <div className="msg">{wallet?.pay_to_configured ? "yes" : "no"}</div>
                </div>
              </div>
              <div className="check-row">
                <span className="status-pass">◆</span>
                <div>
                  <div className="name">Buyer key on server</div>
                  <div className="msg">{wallet?.buyer_address ?? "—"}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Quick links</div>
            <div className="links">
              <a className="btn" href="/api/docs" target="_blank" rel="noreferrer">
                OpenAPI /docs
              </a>
              <a className="btn" href="/api/.well-known/mcp" target="_blank" rel="noreferrer">
                MCP manifest
              </a>
              <a className="btn" href="/api/health" target="_blank" rel="noreferrer">
                /api/health
              </a>
              <a
                className="btn"
                href="https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
      </section>

      <footer className="footer">
        <span>Alpha Sentinel · predictive intelligence, monetized on-chain</span>
        <span className="mono">
          {health?.version ? `api v${health.version}` : "api —"} · refresh 30s
        </span>
      </footer>
    </div>
  );
}
