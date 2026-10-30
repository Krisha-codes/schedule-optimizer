import { useState } from 'react'
import WeekCalendar from './WeekCalendar.jsx'
import { dayString, fmt, shortType } from '../time.js'

const PALETTE = [
  { bg: '#dbeafe', border: '#60a5fa' },
  { bg: '#dcfce7', border: '#4ade80' },
  { bg: '#fef3c7', border: '#fbbf24' },
  { bg: '#fce7f3', border: '#f472b6' },
  { bg: '#ede9fe', border: '#a78bfa' },
  { bg: '#ffedd5', border: '#fb923c' },
  { bg: '#cffafe', border: '#22d3ee' },
  { bg: '#fee2e2', border: '#f87171' },
]

const LABELS = {
  days: 'days on campus',
  spread: 'time on campus',
  early: 'early starts',
  late: 'late finishes',
  instructor: 'instructors',
}

function explain(score) {
  const parts = Object.entries(LABELS)
    .filter(([key]) => score[key] !== 0)
    .map(([key, label]) => `${label} ${score[key]}`)
  return parts.length > 0 ? parts.join(' · ') : 'no penalties'
}

const timedMeetings = (s) => s.meetings.filter((m) => m.start != null && m.end != null)

export default function ScheduleResults({ data, locked, onLock, onAvoid, onUnlock }) {
  const [idx, setIdx] = useState(0)
  const [copied, setCopied] = useState(false)
  const { schedules, message, proven_optimal: provenOptimal } = data

  if (schedules.length === 0) {
    return (
      <div className="card">
        <p>{message}</p>
        <p className="muted">Try relaxing a must-have, or swapping out a course.</p>
      </div>
    )
  }

  const current = schedules[idx]
  const codes = [...new Set(current.sections.map((s) => s.course))].sort()
  const colorOf = (code) => PALETTE[codes.indexOf(code) % PALETTE.length]
  const crns = current.sections.map((s) => s.crn).join(', ')

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(crns)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      window.prompt('Copy these CRNs:', crns)
    }
  }

  return (
    <div className="results">
      <p className="muted">{message}</p>
      {!provenOptimal && (
        <p className="hint">Time limit reached, so the order may not be perfect.</p>
      )}

      <div className="tabs" role="tablist">
        {schedules.map((sch, i) => (
          <button
            key={i}
            type="button"
            role="tab"
            aria-selected={i === idx}
            className={i === idx ? 'tab active' : 'tab'}
            onClick={() => setIdx(i)}
          >
            #{i + 1} <small>score {sch.score.total}</small>
          </button>
        ))}
      </div>
      <p className="muted">
        Score {current.score.total} (lower is better): {explain(current.score)}
      </p>

      <WeekCalendar sections={current.sections} colorOf={colorOf} />

      <div className="card">
        <div className="table-head">
          <h2>Sections</h2>
          <button type="button" onClick={copy}>
            {copied ? 'Copied!' : 'Copy CRNs'}
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Course</th>
                <th>Type</th>
                <th>CRN</th>
                <th>When</th>
                <th>Instructor</th>
                <th>Pin</th>
              </tr>
            </thead>
            <tbody>
              {current.sections.map((s) => {
                const timed = timedMeetings(s)
                const who = [...new Set(s.meetings.flatMap((m) => m.instructors))].join(', ')
                const isLocked = locked.some((p) => p.crn === s.crn)
                return (
                  <tr key={s.crn}>
                    <td>{s.course}</td>
                    <td>{shortType(s.type)}</td>
                    <td className="mono">{s.crn}</td>
                    <td>
                      {timed.length === 0 && <span className="muted">No fixed time</span>}
                      {timed.map((m, i) => (
                        <div key={i}>
                          {dayString(m.days)} {fmt(m.start)}–{fmt(m.end)}
                          {m.building ? ` · ${m.building} ${m.room}` : ''}
                        </div>
                      ))}
                    </td>
                    <td>{who || '—'}</td>
                    <td className="pin-cell">
                      {isLocked ? (
                        <>
                          <span className="state">Locked</span>
                          <button type="button" onClick={() => onUnlock(s.crn)}>
                            Unlock
                          </button>
                        </>
                      ) : (
                        <>
                          <button type="button" onClick={() => onLock(s)}>
                            Lock
                          </button>
                          <button type="button" onClick={() => onAvoid(s)}>
                            Avoid
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="hint">
          Lock a section you already have, or avoid one you can't take, and the schedules update.
          Always confirm CRNs in myPurdue before registering. Linked sections come from Purdue.io
          data and are not an official guarantee.
        </p>
      </div>
    </div>
  )
}
