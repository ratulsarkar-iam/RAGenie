import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'ragenie-search-history'
const MAX_HISTORY = 50

export interface SearchHistoryItem {
  query: string
  timestamp: string
}

export function useSearchHistory() {
  const [history, setHistory] = useState<SearchHistoryItem[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  // Sync to localStorage whenever history changes
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
  }, [history])

  const addToHistory = useCallback((query: string) => {
    setHistory(prev => {
      // Remove duplicate if exists (case-insensitive)
      const filtered = prev.filter(
        item => item.query.toLowerCase() !== query.toLowerCase()
      )
      // Prepend new entry
      const updated = [
        { query, timestamp: new Date().toISOString() },
        ...filtered
      ].slice(0, MAX_HISTORY)
      return updated
    })
  }, [])

  const removeFromHistory = useCallback((query: string) => {
    setHistory(prev => prev.filter(item => item.query !== query))
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
  }, [])

  const searchInHistory = useCallback(
    (term: string): SearchHistoryItem[] => {
      if (!term.trim()) return history
      const lower = term.toLowerCase()
      return history.filter(item =>
        item.query.toLowerCase().includes(lower)
      )
    },
    [history]
  )

  return {
    history,
    addToHistory,
    removeFromHistory,
    clearHistory,
    searchInHistory,
  }
}
