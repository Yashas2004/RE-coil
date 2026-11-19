import { useEffect, useState } from 'react'

export async function getJSON(path) {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`${path} -> ${response.status}`)
  }
  return response.json()
}

// usePolling fetches `path` now and then every `everyMs`, and re-renders with the result.
// It's the whole "live" part of the dashboard: no websockets, just asking again.
export function usePolling(path, everyMs = 3000) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const result = await getJSON(path)
        if (!cancelled) {
          setData(result)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }

    load()
    const timer = setInterval(load, everyMs)
    // Cleanup: stop polling when the component disappears or the path changes.
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [path, everyMs])

  return { data, error }
}

export function percent(value, digits = 1) {
  if (value === null || value === undefined) return '–'
  return (value * 100).toFixed(digits) + '%'
}

export function compact(value) {
  if (value === null || value === undefined) return '–'
  return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}
