export const DAY_LETTERS = 'MTWRFSU'
export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const TYPE_SHORT = {
  Lecture: 'Lec',
  Laboratory: 'Lab',
  Recitation: 'Rec',
  'Practice Study Observation': 'PSO',
  'Distance Learning': 'Online',
}

export const shortType = (type) => TYPE_SHORT[type] ?? type ?? ''

/** "08:30" -> 510. An empty string means "not set" and gives null. */
export function toMinutes(hhmm) {
  if (!hhmm) return null
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

/** 810 -> "1:30 PM" */
export function fmt(mins) {
  if (mins == null) return 'TBA'
  const h = Math.floor(mins / 60)
  const m = mins % 60
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'PM' : 'AM'}`
}

/** [0, 2, 4] -> "MWF" */
export const dayString = (days) => days.map((d) => DAY_LETTERS[d]).join('')