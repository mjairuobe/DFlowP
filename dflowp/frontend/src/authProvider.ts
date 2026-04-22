import type { AuthProvider } from "@refinedev/core";
import {
  clearDflowpApiKeyCookie,
  hasDflowpApiKeyCookie,
  setDflowpApiKeyCookie,
} from "./dflowpApiKeyCookie";

/**
 * Test-Attrappe: kein Abgleich mit Server-Hashed Admin-Credentials. Login prüft das
 * Formular nicht; es setzt nur einen Cookie mit dem in Vite exponierten API-Key
 * (Testkonfiguration, siehe VITE_DFLOWP_API_KEY).
 */
const performTestLogin = async () => {
  const apiKey = import.meta.env.VITE_DFLOWP_API_KEY ?? "";
  setDflowpApiKeyCookie(apiKey);
  return {
    success: true,
    redirectTo: "/",
  };
};

export const authProvider: AuthProvider = {
  login: performTestLogin,
  register: performTestLogin,
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
    if (hasDflowpApiKeyCookie()) {
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
    if (!hasDflowpApiKeyCookie()) {
      return null;
    }

    return {
      id: 1,
      name: "Test",
      avatar: "https://i.pravatar.cc/150",
    };
  },
};
