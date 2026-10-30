import { useEffect, useState } from 'react'
import { searchCourses } from '../api.js'

export default function CoursePicker({ selected, onAdd, onRemove, max = 8 }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')

  const q = query.trim()

  // Search 250 ms after the person stops typing; cancel any request that is still in flight.
  useEffect(() => {
    if (q.length < 2) return undefined
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchCourses(q, controller.signal)
        .then((found) => {
          setResults(found)
          setError('')
        })
        .catch((e) => {
          if (e.name !== 'AbortError') setError(e.message)
        })
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [q])

  const chosen = new Set(selected.map((c) => c.code))
  const shown = q.length >= 2 ? results.filter((c) => !chosen.has(c.code)) : []
  const credits = selected.reduce((sum, c) => sum + (c.credits ?? 0), 0)

  const add = (course) => {
    onAdd(course)
    setQuery('')
    setResults([])
  }

  return (
    <section className="card">
      <h2>Courses</h2>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search, e.g. CS 180 or calculus"
        aria-label="Search courses"
        disabled={selected.length >= max}
      />
      {error && <p className="error">{error}</p>}
      {shown.length > 0 && (
        <ul className="suggestions">
          {shown.map((c) => (
            <li key={c.code}>
              <button type="button" onClick={() => add(c)}>
                <strong>{c.code}</strong> {c.title}
                <span className="muted"> · {c.credits} cr</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected.length === 0 ? (
        <p className="muted">Add the courses you want to take (up to {max}).</p>
      ) : (
        <>
          <ul className="chips">
            {selected.map((c) => (
              <li key={c.code} className="chip" title={c.title}>
                {c.code}
                <button type="button" aria-label={`Remove ${c.code}`} onClick={() => onRemove(c.code)}>
                  ×
                </button>
              </li>
            ))}
          </ul>
          <p className="muted">Total: {credits} credits</p>
        </>
      )}
    </section>
  )
}
