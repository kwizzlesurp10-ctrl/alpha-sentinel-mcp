import { useState, useEffect } from 'react'

interface Stats {
  total_agents: number;
  free_tier_active: number;
  pro_tier_active: number;
  active_tools: string[];
}

function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const API_BASE = import.meta.env.VITE_API_URL || window.location.origin

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 30000) // Update every 30s
    return () => clearInterval(interval)
  }, [])

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/stats`)
      if (!response.ok) throw new Error('Failed to fetch stats')
      const data = await response.json()
      setStats(data)
      setLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <h1>⏳ Loading Alpha Sentinel Mission Control...</h1>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container">
        <h1>❌ Error</h1>
        <p>{error}</p>
        <button onClick={fetchStats}>Retry</button>
      </div>
    )
  }

  return (
    <div className="container">
      <header>
        <h1>🛡️ Alpha Sentinel - Mission Control</h1>
        <p class="tagline">Market Intelligence x402 Dashboard</p>
        <div className="status-indicator">
          <span className="status-dot"></span>
          <span>System Operational</span>
        </div>
      </header>

      {stats && (
        <>
          <div className="stats-grid">
            <div className="stat-card" style={{borderColor: '#6366f1'}}>
              <div className="stat-label">Total Agents</div>
              <div className="stat-value">{stats.total_agents}</div>
            </div>
            <div className="stat-card" style={{borderColor: '#10b981'}}>
              <div className="stat-label">Free Tier Active</div>
              <div className="stat-value">{stats.free_tier_active}</div>
            </div>
            <div className="stat-card" style={{borderColor: '#f59e0b'}}>
              <div className="stat-label">Pro Tier Active</div>
              <div className="stat-value">{stats.pro_tier_active}</div>
            </div>
            <div className="stat-card" style={{borderColor: '#ef4444'}}>
              <div className="stat-label">Active Tools</div>
              <div className="stat-value">{stats.active_tools?.length || 0}</div>
            </div>
          </div>

          {stats.active_tools && stats.active_tools.length > 0 && (
            <div className="tools-section">
              <h2>⚡ Active Tools</h2>
              <ul className="tools-list">
                {stats.active_tools.map(tool => (
                  <li key={tool}>{tool}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="actions">
            <a 
              href={`${window.location.origin}/docs`} 
              className="btn btn-primary"
              target="_blank"
              rel="noopener noreferrer"
            >
              View API Docs
            </a>
            <a 
              href="https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp" 
              className="btn btn-secondary"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub Repository
            </a>
            <button onClick={fetchStats} className="btn btn-secondary">
              🔄 Refresh
            </button>
          </div>
        </>
      )}

      <footer>
        <p>Built by Keith (kwizzlesurp10-ctrl) • Powered by x402 Micropayments</p>
        <p>Predictive intelligence, monetized on-chain ★彡</p>
      </footer>
    </div>
  )
}

export default App
