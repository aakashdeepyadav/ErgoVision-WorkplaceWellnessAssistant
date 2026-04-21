import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ALERT_CONFIG,
  ALERT_FEED_LIMIT,
  HISTORY_LIMIT,
  TOAST_DURATION_MS,
} from '../constants/alerts'

function buildHistoryEntry(sample) {
  return {
    time: new Date().toLocaleTimeString([], { hour12: false }),
    ear: sample.eye?.ear ?? 0,
    blinkRate: sample.eye?.blink_rate ?? 0,
    posture: sample.posture?.deviation ?? 0,
    distance: sample.distance?.distance_cm ?? 0,
    fatigue: sample.fatigue?.fatigue_score ?? 0,
  }
}

export function useErgoVisionSocket(wsUrl) {
  const [connected, setConnected] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState(null)
  const [frame, setFrame] = useState(null)
  const [data, setData] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [toasts, setToasts] = useState([])
  const [history, setHistory] = useState([])
  const [sessionStart, setSessionStart] = useState(null)

  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectAttemptRef = useRef(0)
  const shouldReconnectRef = useRef(true)
  const toastTimersRef = useRef(new Set())

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const removeToast = useCallback((toastId) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== toastId))
  }, [])

  const pushAlert = useCallback((alertType) => {
    const config = ALERT_CONFIG[alertType]
    if (!config) {
      return
    }

    const id = Date.now() + Math.random()
    const timestamp = new Date().toLocaleTimeString([], { hour12: false })

    setAlerts((previous) => [
      {
        id,
        type: alertType,
        label: config.label,
        message: config.message,
        time: timestamp,
        color: config.color,
      },
      ...previous,
    ].slice(0, ALERT_FEED_LIMIT))

    setToasts((previous) => [
      ...previous,
      {
        id,
        label: config.label,
        message: config.message,
        color: config.color,
      },
    ])

    const timer = setTimeout(() => {
      removeToast(id)
      toastTimersRef.current.delete(timer)
    }, TOAST_DURATION_MS)
    toastTimersRef.current.add(timer)
  }, [removeToast])

  const handlePayload = useCallback((payload) => {
    if (payload.frame) {
      setFrame(payload.frame)
    }

    if (!payload.data) {
      return
    }

    setData(payload.data)

    if (payload.data.type !== 'detection') {
      return
    }

    setHistory((previous) => {
      const next = [...previous, buildHistoryEntry(payload.data)]
      return next.length > HISTORY_LIMIT ? next.slice(-HISTORY_LIMIT) : next
    })

    if (payload.data.alerts_fired?.length) {
      payload.data.alerts_fired.forEach(pushAlert)
    }
  }, [pushAlert])

  const connect = useCallback(function connectSocket() {
    const existingSocket = wsRef.current
    if (
      existingSocket &&
      (existingSocket.readyState === WebSocket.OPEN ||
        existingSocket.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    clearReconnectTimer()
    setConnecting(true)
    setError(null)

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setConnecting(false)
      setError(null)
      setSessionStart(new Date())
      reconnectAttemptRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)

        if (payload.type === 'error') {
          setError(payload.message || 'Backend error while initializing monitoring.')
          return
        }

        handlePayload(payload)
      } catch {
        // Ignore malformed payloads and continue the stream.
      }
    }

    ws.onclose = () => {
      setConnected(false)
      setConnecting(false)

      if (shouldReconnectRef.current) {
        const nextAttempt = reconnectAttemptRef.current + 1
        reconnectAttemptRef.current = nextAttempt
        const reconnectDelayMs = Math.min(15000, 1000 * (2 ** (nextAttempt - 1)))

        reconnectTimerRef.current = setTimeout(() => {
          connectSocket()
        }, reconnectDelayMs)
      }
    }

    ws.onerror = () => {
      setError('Cannot connect to ErgoVision backend. Start server.py and try again.')
      setConnecting(false)
    }
  }, [clearReconnectTimer, handlePayload, wsUrl])

  const sendCommand = useCallback((command, payload = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command, ...payload }))
    }
  }, [])

  useEffect(() => {
    shouldReconnectRef.current = true
    connect()
    const activeToastTimers = toastTimersRef.current

    return () => {
      shouldReconnectRef.current = false
      clearReconnectTimer()

      activeToastTimers.forEach((timer) => clearTimeout(timer))
      activeToastTimers.clear()

      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [clearReconnectTimer, connect])

  return {
    connected,
    connecting,
    error,
    frame,
    data,
    alerts,
    toasts,
    history,
    sessionStart,
    connect,
    sendCommand,
  }
}
