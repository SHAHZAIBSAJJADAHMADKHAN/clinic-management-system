export const CLINIC_TIME_ZONE = 'Asia/Karachi'

function timestampTimeParts(value) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: CLINIC_TIME_ZONE,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).formatToParts(new Date(value))

  return Object.fromEntries(parts.filter(({ type }) => type !== 'literal').map(({ type, value: part }) => [type, part]))
}

export function formatTime12Hour(value, { padHour = true } = {}) {
  const timeOnly = typeof value === 'string' && /^(\d{2}):(\d{2})$/.exec(value)
  const time = timeOnly ? null : timestampTimeParts(value)
  const hours = timeOnly ? Number(timeOnly[1]) : Number(time.hour)
  const minutes = timeOnly ? timeOnly[2] : time.minute
  const period = timeOnly ? (hours >= 12 ? 'PM' : 'AM') : time.dayPeriod.toUpperCase()
  const displayHour = hours % 12 || 12

  return `${padHour ? String(displayHour).padStart(2, '0') : displayHour}:${minutes} ${period}`
}

export function formatAppointmentDateTime(value) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: CLINIC_TIME_ZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).formatToParts(new Date(value))
  const date = Object.fromEntries(parts.filter(({ type }) => type !== 'literal').map(({ type, value: part }) => [type, part]))

  return `${date.day} ${date.month} ${date.year}, ${formatTime12Hour(value, { padHour: false })}`
}
