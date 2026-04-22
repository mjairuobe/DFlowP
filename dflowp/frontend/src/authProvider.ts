import type { AuthProvider } from "@refinedev/core";
import {
  clearDflowpApiKeyCookie,
  hasDflowpSessionCookie,
  setDflowpApiKeyCookie,
} from "./dflowpApiKeyCookie";

/**
 * Test-Attrappe: kein Abgleich mit Server-Credentials. Der im Refine-Login
 * eingegebene Wert im Passwortfeld ist der DFlowP-API-Key; derselbe Wert landet
 * im Cookie `dflowp-api-key` und wird als `X-API-Key` an die API gesendet.
 */
const performDflowpTestAuth = async (params: {
  password?: unknown;
}): Promise<{
  success: boolean;
  redirectTo?: string;
  error?: { name: string; message: string };
}> => {
  const raw = params?.password;
  const password = typeof raw === "string" ? raw.trim() : "";
  if (!password) {
    return {
      success: false,
      error: {
        name: "ValidationError",
        message: "Bitte API-Key im Passwortfeld eingeben.",
      },
    };
  }
  setDflowpApiKeyCookie(password);
  return {
    success: true,
    redirectTo: "/",
  };
};

export const authProvider: AuthProvider = {
  login: (params) => performDflowpTestAuth(params),
  register: (params) => performDflowpTestAuth(params),
  updatePassword: async () => {
    return {
      success: true,
    };
  },
  forgotPassword: async () => {
    return {
      success: true,
    };
  },
  logout: async () => {
    clearDflowpApiKeyCookie();
    return {
      success: true,
      redirectTo: "/login",
    };
  },
  onError: async (error) => {
    if (error.response?.status === 401) {
      return {
        logout: true,
      };
    }

    return { error };
  },
  check: async () => {
    if (hasDflowpSessionCookie()) {
      return {
        authenticated: true,
      };
    }

    return {
      authenticated: false,
      error: {
        message: "Check failed",
        name: "API-Key-Cookie not found",
      },
      logout: true,
      redirectTo: "/login",
    };
  },
  getPermissions: async () => null,
  getIdentity: async () => {
    if (!hasDflowpSessionCookie()) {
      return null;
    }

    return {
      id: 1,
      name: "Test",
      avatar: "https://i.pravatar.cc/150",
    };
  },
};
