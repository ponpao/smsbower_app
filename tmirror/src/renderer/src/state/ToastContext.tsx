import { createContext, type ReactNode, useContext } from 'react'
import { useToasts, type ToastItem, type ToastVariant } from './useToasts'

interface ToastContextValue {
  toasts: ToastItem[]
  push: (message: string, variant?: ToastVariant) => void
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const value = useToasts()
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
