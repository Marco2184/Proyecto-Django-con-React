import { useEffect, useState } from 'react'

// Form drafts for the current user only. Never passwords or payment data.
export default function useDraft(key, initial) {
  const [value, setValue] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(key)) ?? initial } catch { return initial }
  })
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(value)) } catch { /* Storage may be disabled. */ } }, [key, value])
  return [value, setValue]
}
