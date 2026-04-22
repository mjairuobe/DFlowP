/**
 * Testkonfiguration: Der Cookie-Wert entspricht dem API-Key, den DFlowP per
 * `X-API-Key` erwartet; der String kommt aus Vite (`VITE_DFLOWP_API_KEY`), nicht aus
 * Formular- oder Server-Credentials-Store.
 */
export const DFLOWP_API_KEY_COOKIE = "dflowp-api-key";

const maxAgeOneYear = 60 * 60 * 24 * 365;

function parseCookies(): Record<string, string> {
  if (typeof document === "undefined") {
    return {};
  }
  return Object.fromEntries(
    document.cookie.split(";").map((part) => {
      const raw = part.trim();
      const eq = raw.indexOf("=");
      const k = eq === -1 ? raw : raw.slice(0, eq);
      const v = eq === -1 ? "" : raw.slice(eq + 1);
      return [k, decodeURIComponent(v)] as [string, string];
    }),
  );
}

export function getDflowpApiKeyFromCookie(): string | undefined {
  const v = parseCookies()[DFLOWP_API_KEY_COOKIE];
  return v !== undefined && v !== "" ? v : undefined;
}

/** Setzt den Cookie; Wert in der Regel aus `import.meta.env.VITE_DFLOWP_API_KEY` (Test-Bundle). */
export function setDflowpApiKeyCookie(value: string): void {
  if (typeof document === "undefined") {
    return;
  }
  const safe = encodeURIComponent(value);
  document.cookie = `${DFLOWP_API_KEY_COOKIE}=${safe}; path=/; max-age=${maxAgeOneYear}; SameSite=Lax`;
}

export function clearDflowpApiKeyCookie(): void {
  if (typeof document === "undefined") {
    return;
  }
  document.cookie = `${DFLOWP_API_KEY_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

export function hasDflowpApiKeyCookie(): boolean {
  return getDflowpApiKeyFromCookie() !== undefined;
}
