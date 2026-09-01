import { useToast } from '../state/ToastContext'

const variantStyles: Record<string, string> = {
  success: 'bg-teal-600 text-white',
  error: 'bg-coral-600 text-white',
  info: 'bg-ink-900 text-white'
}

export function ToastStack(): JSX.Element {
  const { toasts, dismiss } = useToast()

  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-center gap-3 rounded-xl px-4 py-3 shadow-popover ${variantStyles[toast.variant]}`}
          role="status"
        >
          <span className="text-sm font-medium">{toast.message}</span>
          <button
            type="button"
            onClick={() => dismiss(toast.id)}
            className="text-white/70 hover:text-white"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
