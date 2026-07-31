import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import * as authApi from "../api/authApi";
import { clearSession, loadSession } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { AuthSession, LoginRequest, OrganizationRole, RegisterRequest, UserPublic } from "../types/auth";

interface AuthContextValue {
  session: AuthSession | null;
  user: UserPublic | undefined;
  isAuthenticated: boolean;
  isLoadingUser: boolean;
  login: (payload: LoginRequest) => Promise<AuthSession>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  hasAnyRole: (roles: OrganizationRole[]) => boolean;
  isPlatformAdmin: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const queryClient = useQueryClient();

  const userQuery = useQuery({
    queryKey: queryKeys.me(),
    queryFn: authApi.fetchCurrentUser,
    enabled: Boolean(session?.accessToken),
    retry: false,
    staleTime: 60_000,
  });

  const login = useCallback(
    async (payload: LoginRequest) => {
      const nextSession = await authApi.login(payload);
      setSession(nextSession);
      await queryClient.invalidateQueries({ queryKey: queryKeys.me() });
      return nextSession;
    },
    [queryClient],
  );

  const register = useCallback(async (payload: RegisterRequest) => {
    await authApi.register(payload);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearSession();
      setSession(null);
      queryClient.clear();
    }
  }, [queryClient]);

  const hasAnyRole = useCallback(
    (roles: OrganizationRole[]) => {
      if (!session?.role) return false;
      // Platform admin must not silently pass org role checks — System nav uses isPlatformAdmin.
      return roles.includes(session.role);
    },
    [session],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: userQuery.data,
      isAuthenticated: Boolean(session?.accessToken),
      isLoadingUser: userQuery.isLoading,
      login,
      register,
      logout,
      hasAnyRole,
      isPlatformAdmin: session?.platformRole === "platform_admin",
    }),
    [session, userQuery.data, userQuery.isLoading, login, register, logout, hasAnyRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
