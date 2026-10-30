import { shortType } from '../time.js'

export default function Pins({ locked, avoided, onRemove }) {
  if (locked.length === 0 && avoided.length === 0) return null

  return (
    <section className="card">
      <h2>Locked and avoided sections</h2>
      <p className="hint">Locked sections are in every schedule. Avoided sections are never used.</p>
      <ul className="chips">
        {locked.map((p) => (
          <li key={p.crn} className="chip locked">
            <b>Locked</b> {p.course} {shortType(p.type)} · {p.crn}
            <button type="button" aria-label={`Unlock ${p.crn}`} onClick={() => onRemove(p.crn)}>
              ×
            </button>
          </li>
        ))}
        {avoided.map((p) => (
          <li key={p.crn} className="chip avoided">
            <b>Avoid</b> {p.course} {shortType(p.type)} · {p.crn}
            <button
              type="button"
              aria-label={`Stop avoiding ${p.crn}`}
              onClick={() => onRemove(p.crn)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
