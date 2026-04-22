/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Basis-URL der DFlowP-API (ohne Pfad); Endpunkte z. B. `${base}/api/v1/data`. */
  readonly VITE_DFLOWP_API_BASE_URL?: string;
}
