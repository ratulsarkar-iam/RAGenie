import { useEffect, useRef, useState, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  content?: string
  done?: boolean
}

interface UseWebSocketProps {
  url: string
  onMessage: (message: WebSocketMessage) => void
  onError?: (error: Event) => void
  onClose?: () => void
}

export const useWebSocket = ({ url, onMessage, onError, onClose }: UseWebSocketProps) => {
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        onMessage(message)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      if (onError) onError(error)
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
      if (onClose) onClose()
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [url, onMessage, onError, onClose])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.error('WebSocket is not connected')
    }
  }, [])

  return { isConnected, sendMessage }
}
