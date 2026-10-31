// Turn a schedule into an iCalendar (.ics) file that Google Calendar, Apple Calendar and
// Outlook can import. Every meeting becomes one weekly-repeating event.

const TZID = 'America/Indiana/Indianapolis' // Purdue West Lafayette keeps US Eastern time
const BYDAY = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'] // our day numbers: 0 = Monday
const DAY_MS = 86400000

// Tells calendar apps the daylight-saving rules for the time zone used above.
const VTIMEZONE = [
  'BEGIN:VTIMEZONE',
  `TZID:${TZID}`,
  'BEGIN:DAYLIGHT',
  'TZOFFSETFROM:-0500',
  'TZOFFSETTO:-0400',
  'TZNAME:EDT',
  'DTSTART:19700308T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU',
  'END:DAYLIGHT',
  'BEGIN:STANDARD',
  'TZOFFSETFROM:-0400',
  'TZOFFSETTO:-0500',
  'TZNAME:EST',
  'DTSTART:19701101T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU',
  'END:STANDARD',
  'END:VTIMEZONE',
]

const pad = (n) => String(n).padStart(2, '0')
const encoder = new TextEncoder()

/** '2026-08-24' -> a Date at midnight UTC (UTC keeps day arithmetic free of daylight saving). */
function parseDate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

/** Date -> '20260824' */
const compactDate = (date) =>
  `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}`

/** 930 -> '153000' (minutes after midnight -> HHMMSS) */
const compactTime = (mins) => `${pad(Math.floor(mins / 60))}${pad(mins % 60)}00`

/** Our days are 0 = Monday ... 6 = Sunday; JavaScript's are 0 = Sunday ... 6 = Saturday. */
const ourDay = (date) => (date.getUTCDay() + 6) % 7

/** Every date from startIso to endIso (inclusive) that falls on one of `days`. */
function classDates(startIso, endIso, days) {
  const dates = []
  const end = parseDate(endIso).getTime()
  for (let t = parseDate(startIso).getTime(); t <= end; t += DAY_MS) {
    const date = new Date(t)
    if (days.includes(ourDay(date))) dates.push(date)
  }
  return dates
}

/** Escape text the way the iCalendar format requires. */
const esc = (text) =>
  String(text)
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n')

/** Lines may not exceed 75 bytes: longer ones continue on the next line, starting with a space. */
function fold(line) {
  if (encoder.encode(line).length <= 75) return line
  const parts = []
  let current = ''
  let bytes = 0
  for (const ch of line) {
    const size = encoder.encode(ch).length
    const limit = parts.length === 0 ? 75 : 74 // continuation lines begin with one space
    if (bytes + size > limit) {
      parts.push(current)
      current = ''
      bytes = 0
    }
    current += ch
    bytes += size
  }
  parts.push(current)
  return parts.join('\r\n ')
}

const stamp = (now) => now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')

/** The text of the .ics file for these sections (sections without a fixed time are left out). */
export function buildIcs(sections, { termName = '', now = new Date() } = {}) {
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Schedule Optimizer//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
  ]
  if (termName) lines.push(`X-WR-CALNAME:${esc(`${termName} classes`)}`)
  lines.push(...VTIMEZONE)

  for (const s of sections) {
    s.meetings.forEach((m, index) => {
      const timed = m.start != null && m.end != null && m.days.length > 0
      if (!timed || !m.start_date || !m.end_date) return
      const dates = classDates(m.start_date, m.end_date, m.days)
      if (dates.length === 0) return

      const where = [m.building, m.room].filter(Boolean).join(' ')
      const description = [`CRN ${s.crn}`, s.type]
      if (m.instructors.length > 0) description.push(`Instructor: ${m.instructors.join(', ')}`)
      if (termName) description.push(termName)

      lines.push('BEGIN:VEVENT')
      lines.push(`UID:${s.crn}-${index}@schedule-optimizer`)
      lines.push(`DTSTAMP:${stamp(now)}`)
      lines.push(`DTSTART;TZID=${TZID}:${compactDate(dates[0])}T${compactTime(m.start)}`)
      lines.push(`DTEND;TZID=${TZID}:${compactDate(dates[0])}T${compactTime(m.end)}`)
      if (dates.length > 1) {
        // COUNT is the number of class days in the section's date range, so the series ends on time.
        const byDay = [...m.days].sort((a, b) => a - b).map((d) => BYDAY[d]).join(',')
        lines.push(`RRULE:FREQ=WEEKLY;BYDAY=${byDay};COUNT=${dates.length}`)
      }
      lines.push(`SUMMARY:${esc(`${s.course} ${s.type ?? ''}`.trim())}`)
      if (where) lines.push(`LOCATION:${esc(where)}`)
      lines.push(`DESCRIPTION:${esc(description.join('\n'))}`)
      lines.push('END:VEVENT')
    })
  }

  lines.push('END:VCALENDAR')
  return lines.map(fold).join('\r\n') + '\r\n'
}

/** 'Fall 2026', 1 -> 'schedule-fall-2026-1.ics' */
export function icsFilename(termName, rank) {
  const slug = termName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `schedule${slug ? `-${slug}` : ''}-${rank}.ics`
}

/** Offer a text file to the person as a download. */
export function downloadText(filename, text, type = 'text/calendar;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
