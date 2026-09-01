import { useCallback, useRef, useState } from 'react'

export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastItem {
  id: string
  message: string
  variant: ToastVariant
}

export function useToasts(): {
  toasts: ToastItem[]
  push: (message: string, variant?: ToastVariant) => void
  dismiss: (id: string) => void
} {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const counter = useRef(0)

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (message: string, variant: ToastVariant = 'info') => {
      counter.current += 1
      const id = `toast-${counter.current}`
      setToasts((prev) => [...prev, { id, message, variant }])
      setTimeout(() => dismiss(id), 4200)
    },
    [dismiss]
  )

  return { toasts, push, dismiss }
}
