async function get(path) {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`${path}: ${r.status}`)
  return r.json()
}

export const getSummary = (days) => get(`/api/summary?days=${days}`)
export const getSeries = (metric, days) => get(`/api/series/${metric}?days=${days}`)
export const getSleep = (days) => get(`/api/sleep?days=${days}`)
export const getImportJob = (id) => get(`/api/import/${id}`)
export const getWorkouts = (days) => get(`/api/workouts?days=${days}`)
export const getWorkout = (id) => get(`/api/workouts/${encodeURIComponent(id)}`)

export async function uploadImport(file, apiKey) {
  const form = new FormData()
  form.append('file', file)
  const r = await fetch('/api/import', {
    method: 'POST',
    headers: { 'X-API-Key': apiKey },
    body: form,
  })
  if (!r.ok) throw new Error(r.status === 401 ? 'Wrong API key' : `Upload failed (${r.status})`)
  return r.json()
}
