// Auth context — stores login state and JWT
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import type { User } from "../lib/types";
import { recordAudit } from "../lib/auditLog";

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("vb_token"));
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("vb_token");
    setToken(null);
    setUser(null);
  }, []);

  // Load user profile on mount if token exists
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    api.me()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [token, logout]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api.login(email, password);
    localStorage.setItem("vb_token", data.access_token);
    setToken(data.access_token);
    const me = await api.me();
    setUser(me);
    void recordAudit({
      actorId: me.email,
      actorRole: me.role,
      eventType: "AUTH_LOGIN",
      subject: me.hospital_id ?? "DEFAULT_HOSP",
      detail: `Authenticated as ${me.full_name}`,
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
