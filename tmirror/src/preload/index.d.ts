import type { TmirrorApi } from './index'

declare global {
  interface Window {
    tmirror: TmirrorApi
  }
}
