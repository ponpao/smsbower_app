import { useCallback, useEffect, useRef, useState } from 'react'
import type { Device } from '@shared/types'

const POLL_MS = 3000

export function useDevices(): {
  devices: Device[]
  loading: boolean
  refresh: () => Promise<void>
  setMirroring: (serial: string, mirroring: boolean) => void
} {
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const mirroringSerials = useRef<Set<string>>(new Set())

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const list = await window.tmirror.devices.list()
      setDevices(list.map((d) => ({ ...d, isMirroring: mirroringSerials.current.has(d.serial) })))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, POLL_MS)
    return () => clearInterval(interval)
  }, [refresh])

  const setMirroring = useCallback((serial: string, mirroring: boolean) => {
    if (mirroring) mirroringSerials.current.add(serial)
    else mirroringSerials.current.delete(serial)
    setDevices((prev) => prev.map((d) => (d.serial === serial ? { ...d, isMirroring: mirroring } : d)))
  }, [])

  return { devices, loading, refresh, setMirroring }
}
