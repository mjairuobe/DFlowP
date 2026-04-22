/**
 * Testkonfiguration: Der Cookie-Wert ist der DFlowP-API-Key (dasselbe, was die API
 * per `X-API-Key` erwartet). Eingabe im Refine-Login: Passwortfeld → Cookie
 * `dflowp-api-key` → Header für HTTP-Requests.
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

/**
 * Roher Wert, nur wenn der Cookie-Name existiert. Leerer String = eingeloggt ohne Key
 * (für X-API-Key wird nichts gesendet).
 */
function getDflowpApiKeyRawFromCookie(): string | undefined {
  const map = parseCookies();
  if (!Object.prototype.hasOwnProperty.call(map, DFLOWP_API_KEY_COOKIE)) {
    return undefined;
  }
  return map[DFLOWP_API_KEY_COOKIE] ?? "";
}

/** Liefert den Key für `X-API-Key` nur, wenn inhaltlich gesetzt. */
export function getDflowpApiKeyForHeader(): string | undefined {
  const raw = getDflowpApiKeyRawFromCookie();
  if (raw === undefined) {
    return undefined;
  }
  return raw === "" ? undefined : raw;
}

export function hasDflowpSessionCookie(): boolean {
  return getDflowpApiKeyRawFromCookie() !== undefined;
}

/** Setzt den Cookie (Testflow: Wert = API-Key aus dem Refine-Login-Passwortfeld). */
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
