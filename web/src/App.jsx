import { useEffect, useState } from 'react'
import { getSummary, getSeries, getSleep, uploadImport, getImportJob } from './api'
import { Sparkline, BandChart, SleepBars, Columns, TableView } from './charts'
import { fmtValue, fmtHours } from './chart-utils'

const RANGES = [7, 30, 90]

function readinessSentence(components) {
  if (!components) return ''
  const parts = []
  if (components.hrv != null)
    parts.push(components.hrv < -1 ? 'HRV below your normal range' : 'HRV inside your normal range')
  if (components.rhr != null)
    parts.push(components.rhr > 1 ? 'resting heart rate above normal' : 'resting heart rate normal')
  return parts.length ? parts.join('; ') + '.' : 'Not enough history yet for a baseline.'
}

function syncAge(lastSync) {
  if (!lastSync) return { label: 'no data yet', stale: true }
  const t = new Date(lastSync.replace(' +', '+').replace(' ', 'T'))
  const hours = (Date.now() - t.getTime()) / 3.6e6
  const label = hours < 1 ? 'synced <1h ago' : `synced ${Math.round(hours)}h ago`
  return { label, stale: hours > 24 }
}

function Tile({ label, value, delta, deltaGood, sub, spark, hero }) {
  return (
    <div className={hero ? 'tile hero' : 'tile'}>
      <div className="label">{label}</div>
      <div>
        <span className="value">{value}</span>
        {delta && <span className={`delta ${deltaGood ? 'up' : 'down'}`}>{delta}</span>}
      </div>
      {hero && value !== '–' && (
        <div className="meter"><div style={{ width: `${value}%` }} /></div>
      )}
      {sub && <div className="sub">{sub}</div>}
      {spark && <Sparkline values={spark} w={140} h={30} />}
    </div>
  )
}

function DomainRow({ icon, name, headline, spark, open, onToggle, children }) {
  return (
    <div className={open ? 'row open' : 'row'}>
      <div className="rowhead" onClick={onToggle}>
        <span className="icon">{icon}</span>
        <span className="name">{name}</span>
        <span className="headline" dangerouslySetInnerHTML={{ __html: headline }} />
        <Sparkline values={spark} />
        <span className="chev">›</span>
      </div>
      {open && <div className="rowbody">{children}</div>}
    </div>
  )
}

function SleepBody({ days }) {
  const [nights, setNights] = useState(null)
  useEffect(() => { getSleep(days).then((r) => setNights(r.nights)) }, [days])
  if (!nights) return <p className="empty">Loading…</p>
  const shown = nights.slice(-30)
  return (
    <>
      <h3>Stages per night</h3>
      <SleepBars nights={shown} />
      <TableView cols={['night', 'deep h', 'core h', 'REM h', 'awake h']}
        rows={nights.slice(-7).map((n) => [n.date, n.deep_h, n.core_h, n.rem_h, n.awake_h])} />
    </>
  )
}

function HeartBody({ days }) {
  const [rhr, setRhr] = useState(null)
  const [hrv, setHrv] = useState(null)
  useEffect(() => {
    getSeries('resting_heart_rate', days).then((r) => setRhr(r.points))
    getSeries('heart_rate_variability', days).then((r) =>
      r.points.length ? setHrv(r.points)
        : getSeries('heart_rate_variability_sdnn', days).then((r2) => setHrv(r2.points)))
  }, [days])
  return (
    <div className="charts2">
      <div>
        <h3>Resting heart rate <span className="soft">bpm · band = your 30-day normal</span></h3>
        <BandChart points={rhr} label="RHR" />
      </div>
      <div>
        <h3>HRV (SDNN) <span className="soft">ms · overnight</span></h3>
        <BandChart points={hrv} label="HRV" unit=" ms" />
      </div>
    </div>
  )
}

function ActivityBody({ days }) {
  const [steps, setSteps] = useState(null)
  useEffect(() => { getSeries('step_count', days).then((r) => setSteps(r.points)) }, [days])
  return (
    <>
      <h3>Steps per day</h3>
      <Columns points={steps?.slice(-30)} goal={8000} />
    </>
  )
}

function BodyVitalsBody({ days }) {
  const [temp, setTemp] = useState(null)
  const [spo2, setSpo2] = useState(null)
  const [resp, setResp] = useState(null)
  useEffect(() => {
    getSeries('apple_sleeping_wrist_temperature', days).then((r) => setTemp(r.points))
    getSeries('oxygen_saturation', days).then((r) =>
      setSpo2(r.points.map((p) => ({ ...p, value: p.value * 100, lo: p.lo * 100, hi: p.hi * 100 }))))
    getSeries('respiratory_rate', days).then((r) => setResp(r.points))
  }, [days])
  return (
    <div className="charts3">
      <div><h3>Wrist temperature °C</h3><BandChart points={temp} label="Temp" unit="°" w={250} /></div>
      <div><h3>SpO₂</h3><BandChart points={spo2} label="SpO₂" unit="%" w={250} /></div>
      <div><h3>Respiratory rate /min</h3><BandChart points={resp} label="Resp" w={250} /></div>
    </div>
  )
}

function ImportPage({ onBack }) {
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey') || '')
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleFile(file) {
    if (!file) return
    setError(null); setBusy(true)
    localStorage.setItem('apiKey', apiKey)
    try {
      const { job_id } = await uploadImport(file, apiKey)
      let j
      do {
        await new Promise((r) => setTimeout(r, 700))
        j = await getImportJob(job_id)
        setJob(j)
      } while (j.status === 'running' || j.status === 'queued')
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="importpage">
      <h2>Import data file</h2>
      <p className="soft">
        Upload an Apple Health <b>export.zip</b> (iPhone: Health app → profile → Export All Health
        Data) or a Health Auto Export JSON file. Re-importing the same file is safe — rows are
        deduplicated.
      </p>
      <label className="field">API key
        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
          placeholder="same key HAE uses" />
      </label>
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files[0]) }}
      >
        <p>Drop export.zip here, or</p>
        <input type="file" accept=".zip,.xml,.json"
          onChange={(e) => handleFile(e.target.files[0])} />
      </div>
      {busy && <p>Importing… {job?.parsed ? `${job.parsed.toLocaleString()} records parsed` : ''}</p>}
      {job?.status === 'done' && (
        <p className="ok">
          Done: {job.counts.samples?.toLocaleString()} samples, {job.counts.sleep_nights} nights,{' '}
          {job.counts.workouts} workouts.
        </p>
      )}
      {(error || job?.status === 'error') && <p className="err">{error || job.error}</p>}
      <button className="ghost" onClick={onBack}>← Back to dashboard</button>
    </div>
  )
}

export default function App() {
  const [days, setDays] = useState(30)
  const [summary, setSummary] = useState(null)
  const [open, setOpen] = useState({ sleep: true })
  const [page, setPage] = useState('dash')
  const [theme, setTheme] = useState(localStorage.getItem('theme') || '')

  useEffect(() => {
    if (theme) document.documentElement.setAttribute('data-theme', theme)
    else document.documentElement.removeAttribute('data-theme')
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    if (page === 'dash') getSummary(days).then(setSummary).catch(() => setSummary(null))
  }, [days, page])

  if (page === 'import') return <div className="wrap"><ImportPage onBack={() => setPage('dash')} /></div>

  const s = summary
  const sync = syncAge(s?.last_sync)
  const d = s?.domains
  const today = new Date().toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <div className="wrap">
      <div className="top">
        <h1>Watch Dashboard</h1>
        <span className="date">{today}</span>
        <span className="spacer" />
        <span className={sync.stale ? 'pill stale' : 'pill'}>
          <span className="dot" />{sync.label}
        </span>
        <button className="ghost" onClick={() => setPage('import')}>⬆ Import file</button>
        <button className="ghost" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>◐ Theme</button>
      </div>

      <div className="scores">
        <Tile hero label="Readiness" value={s?.readiness.score ?? '–'}
          sub={readinessSentence(s?.readiness.components)} />
        <Tile label="Sleep score" value={s?.sleep_score.score ?? '–'} spark={d?.sleep.spark} />
        <Tile label="Exercise this week" value={s?.exercise_week.minutes ?? '–'}
          delta="min" spark={s?.exercise_week.spark} />
      </div>

      <div className="filters">
        {RANGES.map((r) => (
          <button key={r} className={r === days ? 'fbtn active' : 'fbtn'} onClick={() => setDays(r)}>
            {r}d
          </button>
        ))}
        <span className="note">range applies to all charts below</span>
      </div>

      <DomainRow icon="🛌" name="Sleep" spark={d?.sleep.spark}
        headline={`<b>${fmtHours(d?.sleep.last_night_h)}</b> last night`}
        open={!!open.sleep} onToggle={() => setOpen((o) => ({ ...o, sleep: !o.sleep }))}>
        <SleepBody days={days} />
      </DomainRow>

      <DomainRow icon="❤️" name="Heart" spark={d?.heart.spark}
        headline={`RHR <b>${fmtValue(d?.heart.rhr)}</b> · HRV <b>${fmtValue(d?.heart.hrv)} ms</b>`}
        open={!!open.heart} onToggle={() => setOpen((o) => ({ ...o, heart: !o.heart }))}>
        <HeartBody days={days} />
      </DomainRow>

      <DomainRow icon="🏃" name="Activity" spark={d?.activity.spark}
        headline={`<b>${fmtValue(d?.activity.steps_today)}</b> steps today`}
        open={!!open.activity} onToggle={() => setOpen((o) => ({ ...o, activity: !o.activity }))}>
        <ActivityBody days={days} />
      </DomainRow>

      <DomainRow icon="🌡️" name="Body & vitals" spark={d?.body.spark}
        headline={`temp <b>${d?.body.temp_dev == null ? '–' : (d.body.temp_dev >= 0 ? '+' : '') + d.body.temp_dev + '°'}</b> · SpO₂ <b>${d?.body.spo2 == null ? '–' : Math.round(d.body.spo2 * 100) + '%'}</b>`}
        open={!!open.body} onToggle={() => setOpen((o) => ({ ...o, body: !o.body }))}>
        <BodyVitalsBody days={days} />
      </DomainRow>

      <div className="foot">
        <span>Coming in v2: workouts &amp; GPS · noise · mindfulness</span>
      </div>
    </div>
  )
}
