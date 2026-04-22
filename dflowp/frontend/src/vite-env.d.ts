/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_MAP_ID: string;
  /** Basis-URL für Bestellungen (Finefoods / simple-rest), z. B. https://api.finefoods.refine.dev */
  readonly VITE_ORDERS_API_BASE_URL?: string;
  /** Basis-URL der DFlowP-API (ohne Pfad); Endpunkte z. B. `${base}/api/v1/data`. */
  readonly VITE_DFLOWP_API_BASE_URL?: string;
}
