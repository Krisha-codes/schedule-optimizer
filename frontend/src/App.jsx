import { useEffect, useState } from 'react'
import { buildSchedules, getTerm } from './api.js'
import CoursePicker from './components/CoursePicker.jsx'
import Controls from './components/Controls.jsx'
import Pins from './components/Pins.jsx'
import ScheduleResults from './components/ScheduleResults.jsx'
import { toMinutes } from './time.js'
import './App.css'

const DEFAULTS = {
  earliest: '',
  latest: '',
  freeDays: [],
  prefStart: '09:00',
  prefEnd: '17:00',
  wDays: 60,
  wSpread: 1,
  variety: 3,
}

const pinEntry = (s) => ({ crn: s.crn, course: s.course, type: s.type })
const withEntry = (list, entry) =>
  list.some((x) => x.crn === entry.crn) ? list : [...list, entry]
const without = (list, crn) => list.filter((x) => x.crn !== crn)

export default function App() {
  const [term, setTerm] = useState(null)
  const [selected, setSelected] = useState([])
  const [locked, setLocked] = useState([])
  const [avoided, setAvoided] = useState([])
  const [settings, setSettings] = useState(DEFAULTS)
  const [run, setRun] = useState({ status: 'idle', id: 0 })

  useEffect(() => {
    getTerm()
      .then(setTerm)
      .catch(() => {
        // the header just stays empty if the backend is down; generating will explain why
      })
  }, [])

  const update = (patch) => setSettings((s) => ({ ...s, ...patch }))
  const addCourse = (course) =>
    setSelected((list) => (list.some((c) => c.code === course.code) ? list : [...list, course]))
  const removeCourse = (code) => {
    setSelected((list) => list.filter((c) => c.code !== code))
    // locks and avoids only make sense for courses that are still selected
    setLocked((list) => list.filter((p) => p.course !== code))
    setAvoided((list) => list.filter((p) => p.course !== code))
  }

  const generate = async (pins = { locked, avoided }) => {
    const id = run.id + 1
    setRun({ status: 'loading', id })
    try {
      const data = await buildSchedules({
        courses: selected.map((c) => c.code),
        constraints: {
          earliest_start: toMinutes(settings.earliest),
          latest_end: toMinutes(settings.latest),
          free_days: settings.freeDays,
          required_crns: pins.locked.map((p) => p.crn),
          avoid_crns: pins.avoided.map((p) => p.crn),
        },
        preferences: {
          preferred_start: toMinutes(settings.prefStart) ?? 9 * 60,
          preferred_end: toMinutes(settings.prefEnd) ?? 17 * 60,
          w_days: settings.wDays,
          w_spread: settings.wSpread,
        },
        top_n: 5,
        min_difference: settings.variety,
      })
      setRun({ status: 'done', id, data })
    } catch (e) {
      setRun({ status: 'error', id, error: e.message })
    }
  }

  // Change the locked/avoided lists, and refresh the schedules if some are on screen.
  const applyPins = (nextLocked, nextAvoided) => {
    setLocked(nextLocked)
    setAvoided(nextAvoided)
    if (run.status === 'done' || run.status === 'error') {
      generate({ locked: nextLocked, avoided: nextAvoided })
    }
  }
  const lock = (s) => applyPins(withEntry(locked, pinEntry(s)), without(avoided, s.crn))
  const avoid = (s) => applyPins(without(locked, s.crn), withEntry(avoided, pinEntry(s)))
  const unpin = (crn) => applyPins(without(locked, crn), without(avoided, crn))

  return (
    <div className="app">
      <header>
        <h1>Schedule Optimizer</h1>
        {term && (
          <p className="muted">
            Term {term.term_code} · {term.campus} · {term.courses} courses loaded
          </p>
        )}
      </header>

      <div className="layout">
        <aside>
          <CoursePicker selected={selected} onAdd={addCourse} onRemove={removeCourse} />
          <Pins locked={locked} avoided={avoided} onRemove={unpin} />
          <Controls settings={settings} update={update} />
          <button
            type="button"
            className="primary"
            disabled={selected.length === 0 || run.status === 'loading'}
            onClick={() => generate()}
          >
            {run.status === 'loading' ? 'Working…' : 'Find best schedules'}
          </button>
        </aside>

        <main>
          {run.status === 'idle' && (
            <p className="muted placeholder">
              Pick your courses, set your rules, then press “Find best schedules”.
            </p>
          )}
          {run.status === 'loading' && <p className="muted placeholder">Finding the best schedules…</p>}
          {run.status === 'error' && <p className="error placeholder">{run.error}</p>}
          {run.status === 'done' && (
            <ScheduleResults
              key={run.id}
              data={run.data}
              locked={locked}
              onLock={lock}
              onAvoid={avoid}
              onUnlock={unpin}
            />
          )}
        </main>
      </div>
    </div>
  )
}
