// In development, calls use relative URLs (/api/...) and Vite forwards them to the backend.
// In the deployed site, VITE_API_URL holds the server address (for example https://my-api.onrender.com).
const API = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')

async function request(url, options) {
  let res
  try {
    res = await fetch(API + url, options)
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error("Can't reach the server. Is the backend running?", { cause: e })
  }

  if (!res.ok) {
    let detail =
      res.status >= 500
        ? `The server had a problem (error ${res.status}). Is the backend running?`
        : `Request failed (error ${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) detail = body.detail[0].msg
    } catch {
      // the error response was not JSON; keep the generic message
    }
    throw new Error(detail)
  }
  return res.json()
}

export const getTerms = () => request('/api/terms')

export const getTerm = (term) => request(`/api/term?term=${encodeURIComponent(term)}`)

export const searchCourses = (q, term, signal) =>
  request(
    `/api/courses?term=${encodeURIComponent(term)}&q=${encodeURIComponent(q)}&limit=8`,
    { signal },
  )

export const buildSchedules = (payload, term) =>
  request(`/api/schedules?term=${encodeURIComponent(term)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
