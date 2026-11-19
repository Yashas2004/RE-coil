import { useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { compact, percent, usePolling } from './api.js'

const VARIANT_COLORS = { model: '#ff4d6d', control: '#7aa2f7', random: '#6b7280' }

export default function App() {
  return (
    <div className="page">
      <Header />
      <Stats />
      <div className="grid two">
        <WatchRateChart />
        <ABPanel />
      </div>
      <div className="grid two">
        <TrainingRuns />
        <Trending />
      </div>
      <FeedInspector />
      <footer>RE-coil · two-tower retrieval · multi-stage ranking · streaming retrain loop</footer>
    </div>
  )
}

function Header() {
  const { data } = usePolling('/api/overview', 3000)
  const model = data?.model
  const live = model && model.version

  return (
    <header>
      <div>
        <h1>RE-coil</h1>
        <p className="muted">A recommender that retrains itself from what users do</p>
      </div>
      <div className={`badge ${live ? 'ok' : 'warn'}`}>
        <span className="dot" />
        {live ? `serving ${model.version}` : 'no model yet'}
      </div>
    </header>
  )
}

function Stats() {
  const { data } = usePolling('/api/overview', 3000)
  const cards = [
    ['Videos', compact(data?.videos)],
    ['Users', compact(data?.users)],
    ['Interactions', compact(data?.interactions)],
    ['Events / sec', data ? data.events_per_sec.toFixed(1) : '–'],
    ['Live model AUC', data?.model?.auc ? data.model.auc.toFixed(3) : '–'],
  ]
  return (
    <div className="stats">
      {cards.map(([label, value]) => (
        <div className="card stat" key={label}>
          <div className="muted small">{label}</div>
          <div className="big">{value}</div>
        </div>
      ))}
    </div>
  )
}

// The API returns one row per (minute, variant). Recharts wants one row per minute
// with a column per variant, so we "pivot" it here.
function pivotByMinute(points) {
  const byMinute = {}
  for (const point of points) {
    const label = new Date(point.minute).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    if (!byMinute[label]) byMinute[label] = { minute: label }
    byMinute[label][point.variant] = point.rate
  }
  return Object.values(byMinute)
}

function WatchRateChart() {
  const { data } = usePolling('/api/watch-rate?minutes=30', 5000)
  const rows = data ? pivotByMinute(data) : []

  return (
    <section className="card">
      <h2>Watch rate per minute</h2>
      <p className="muted small">Share of shown videos the bots actually watched. Higher = better feed.</p>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows}>
          <CartesianGrid stroke="#2a2f3a" strokeDasharray="3 3" />
          <XAxis dataKey="minute" stroke="#8b93a7" fontSize={12} />
          <YAxis stroke="#8b93a7" fontSize={12} domain={[0, 0.8]} tickFormatter={(v) => percent(v, 0)} />
          <Tooltip formatter={(v) => percent(v)} contentStyle={{ background: '#151922', border: '1px solid #2a2f3a' }} />
          <Legend />
          {Object.entries(VARIANT_COLORS).map(([variant, color]) => (
            <Line key={variant} type="monotone" dataKey={variant} stroke={color}
              strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </section>
  )
}

function ABPanel() {
  const { data } = usePolling('/api/ab?minutes=15', 5000)
  const variants = data?.variants ?? []
  const lift = data?.lift

  return (
    <section className="card">
      <h2>A/B test · last 15 min</h2>
      <p className="muted small">10% of users are held out on a trending-only feed (control).</p>
      <div className="lift">
        <div className="muted small">Model lift over control</div>
        <div className={`huge ${lift > 0 ? 'good' : ''}`}>
          {lift === null || lift === undefined ? '–' : (lift > 0 ? '+' : '') + percent(lift, 0)}
        </div>
      </div>
      {variants.map((row) => (
        <div className="bar-row" key={row.variant}>
          <span className="bar-label">{row.variant}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: percent(row.rate), background: VARIANT_COLORS[row.variant] }} />
          </div>
          <span className="bar-value">{percent(row.rate)}</span>
          <span className="muted small">{compact(row.users)} users</span>
        </div>
      ))}
    </section>
  )
}

function TrainingRuns() {
  const { data } = usePolling('/api/training-runs?limit=12', 5000)
  return (
    <section className="card">
      <h2>Training runs</h2>
      <p className="muted small">Every retrain, and whether it cleared the 0.65 AUC gate.</p>
      <table>
        <thead>
          <tr><th>Version</th><th>Samples</th><th>AUC</th><th></th></tr>
        </thead>
        <tbody>
          {(data ?? []).map((run) => (
            <tr key={run.version}>
              <td className="mono">{run.version}</td>
              <td>{compact(run.samples)}</td>
              <td>
                <div className="auc">
                  <div className="auc-fill" style={{ width: `${Math.max(0, (run.auc - 0.5) * 200)}%` }} />
                  <span>{run.auc.toFixed(3)}</span>
                </div>
              </td>
              <td><span className={`tag ${run.promoted ? 'ok' : 'warn'}`}>{run.promoted ? 'promoted' : 'rejected'}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Trending() {
  const { data } = usePolling('/api/trending', 5000)
  return (
    <section className="card">
      <h2>Trending now</h2>
      <p className="muted small">Best smoothed watch rate, this hour + last hour. A rate, not a count: shown-a-lot isn't the same as good.</p>
      <ol className="trending">
        {(data ?? []).map((item) => (
          <li key={item.video_id}>
            <span className={`chip cat-${item.category}`}>{item.category}</span>
            <span className="title">{item.title || item.video_id}</span>
            <span className="muted small">{percent(item.watch_rate, 0)} watched</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

function FeedInspector() {
  const [input, setInput] = useState('u000000')
  const [userId, setUserId] = useState('u000000')
  const { data, error } = usePolling(`/api/feed?user_id=${encodeURIComponent(userId)}`, 5000)

  return (
    <section className="card">
      <div className="row">
        <div>
          <h2>Feed inspector</h2>
          <p className="muted small">The exact feed this user would get right now. Refreshes every 5s.</p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); setUserId(input.trim()) }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="user id" />
          <button type="submit">Show feed</button>
        </form>
      </div>
      {error && <p className="warn-text">Couldn't load feed: {error}</p>}
      {data && (
        <>
          <p className="muted small">
            served by <span className="mono">{data.model_version}</span> in {data.latency_ms?.toFixed(1)} ms
          </p>
          <div className="feed">
            {data.items.map((item, index) => (
              <div className="feed-item" key={item.video_id}>
                <div className="muted small">#{index + 1}</div>
                <div className="mono">{item.video_id}</div>
                {item.category && <span className={`chip cat-${item.category}`}>{item.category}</span>}
                <div className="small">p(watch) {item.p_watch ? percent(item.p_watch, 0) : '–'}</div>
                <span className={`tag src-${item.source}`}>{item.source}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
