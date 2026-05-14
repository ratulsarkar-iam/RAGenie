export interface WebSocketMessage {
  type: 'user_message' | 'assistant_message' | 'stream_start' | 'stream_token' | 'stream_end' | 'error' | 'reasoning' | 'tool_call' | 'tool_result' | 'tool_error'
  content?: string
  done?: boolean
  tool?: string
  args?: string
  result?: string
  error?: string
}

export class ChatWebSocket {
  private ws: WebSocket | null = null
  private clientId: string
  private messageHandlers: ((message: WebSocketMessage) => void)[] = []
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000

  constructor(clientId: string = Math.random().toString(36).substring(7)) {
    this.clientId = clientId
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      // Use same host - Vite proxy will route /ws to backend
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/${this.clientId}`

      console.log('Connecting to WebSocket:', wsUrl)
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.reconnectAttempts = 0
        resolve()
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.messageHandlers.forEach(handler => handler(message))
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        reject(error)
      }

      this.ws.onclose = () => {
        console.log('WebSocket disconnected')
        this.attemptReconnect()
      }
    })
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      
      setTimeout(() => {
        this.connect().catch(err => {
          console.error('Reconnection failed:', err)
        })
      }, this.reconnectDelay * this.reconnectAttempts)
    }
  }

  sendMessage(message: string, conversationId: string = 'default', useAgent: boolean = false, useReasoning: boolean = false) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        message,
        conversation_id: conversationId,
        use_agent: useAgent,
        use_reasoning: useReasoning
      }))
    } else {
      console.error('WebSocket is not connected')
      throw new Error('WebSocket is not connected')
    }
  }

  onMessage(handler: (message: WebSocketMessage) => void) {
    this.messageHandlers.push(handler)
  }

  removeMessageHandler(handler: (message: WebSocketMessage) => void) {
    this.messageHandlers = this.messageHandlers.filter(h => h !== handler)
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.messageHandlers = []
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}
