import { DAY_NAMES, fmt, shortType } from '../time.js'

const HOUR_PX = 52

export default function WeekCalendar({ sections, colorOf }) {
  // One block per meeting per day. Sections with no fixed time go in a note under the grid.
  const blocks = []
  const untimed = []
  for (const s of sections) {
    const timed = s.meetings.filter((m) => m.start != null && m.end != null && m.days.length > 0)
    if (timed.length === 0) untimed.push(s)
    for (const m of timed) {
      for (const day of m.days) blocks.push({ day, m, s })
    }
  }

  const gridStart = Math.floor(Math.min(8 * 60, ...blocks.map((b) => b.m.start)) / 60) * 60
  const gridEnd = Math.ceil(Math.max(17 * 60, ...blocks.map((b) => b.m.end)) / 60) * 60
  const lastDay = Math.max(4, ...blocks.map((b) => b.day))
  const days = Array.from({ length: lastDay + 1 }, (_, i) => i)
  const hours = Array.from({ length: (gridEnd - gridStart) / 60 }, (_, i) => gridStart / 60 + i)
  const px = (mins) => ((mins - gridStart) / 60) * HOUR_PX
  const bodyHeight = px(gridEnd)

  return (
    <div className="cal-wrap">
      <div
        className="cal"
        style={{ gridTemplateColumns: `52px repeat(${days.length}, minmax(0, 1fr))` }}
      >
        <div className="cal-corner" />
        {days.map((d) => (
          <div key={d} className="cal-head">
            {DAY_NAMES[d]}
          </div>
        ))}

        <div className="cal-axis" style={{ height: bodyHeight }}>
          {hours.map((h) => (
            <span key={h} style={{ top: px(h * 60) + 2 }}>
              {fmt(h * 60).replace(':00', '')}
            </span>
          ))}
        </div>

        {days.map((d) => (
          <div key={d} className="cal-col" style={{ height: bodyHeight, '--hour': `${HOUR_PX}px` }}>
            {blocks
              .filter((b) => b.day === d)
              .map((b, i) => {
                const color = colorOf(b.s.course)
                const who = b.m.instructors.join(', ')
                return (
                  <div
                    key={`${b.s.crn}-${i}`}
                    className="cal-block"
                    style={{
                      top: px(b.m.start),
                      height: px(b.m.end) - px(b.m.start),
                      background: color.bg,
                      borderColor: color.border,
                    }}
                    title={`${b.s.course} ${b.s.type} (CRN ${b.s.crn})\n${fmt(b.m.start)} - ${fmt(b.m.end)}${who ? `\n${who}` : ''}`}
                  >
                    <strong>{b.s.course}</strong> {shortType(b.s.type)}
                    <div>
                      {fmt(b.m.start)} – {fmt(b.m.end)}
                    </div>
                    {b.m.building && (
                      <div>
                        {b.m.building} {b.m.room}
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
        ))}
      </div>
      {untimed.length > 0 && (
        <p className="muted">
          No fixed meeting time:{' '}
          {untimed.map((s) => `${s.course} ${shortType(s.type)} (CRN ${s.crn})`).join(', ')}
        </p>
      )}
    </div>
  )
}
