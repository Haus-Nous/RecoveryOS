"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  UserResponse,
  MerchantSummaryResponse,
  fetchCurrentUser,
  fetchUserMerchants,
} from "./api-client";

export interface AuthContextType {
  user: UserResponse | null;
  merchants: MerchantSummaryResponse[];
  activeMerchant: MerchantSummaryResponse | null;
  isLoading: boolean;
  error: string | null;
  setActiveMerchantId: (id: string) => void;
  refreshAuth: () => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [merchants, setMerchants] = useState<MerchantSummaryResponse[]>([]);
  const [activeMerchantId, setActiveMerchantId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // In production, token is retrieved on-demand from cookie/session provider.
  // In development/test mode, reads NEXT_PUBLIC_DEV_AUTH_TOKEN if configured.
  const getToken = useCallback((): string | null => {
    if (typeof window !== "undefined") {
      return process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN || null;
    }
    return null;
  }, []);

  const refreshAuth = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setMerchants([]);
      setActiveMerchantId(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const [userData, merchantList] = await Promise.all([
        fetchCurrentUser(token),
        fetchUserMerchants(token),
      ]);

      setUser(userData);
      setMerchants(merchantList);
      if (merchantList.length > 0 && !activeMerchantId) {
        setActiveMerchantId(merchantList[0].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication failed";
      setError(msg);
      setUser(null);
      setMerchants([]);
    } finally {
      setIsLoading(false);
    }
  }, [getToken, activeMerchantId]);

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  const signOut = useCallback(() => {
    setUser(null);
    setMerchants([]);
    setActiveMerchantId(null);
  }, []);

  const activeMerchant =
    merchants.find((m) => m.id === activeMerchantId) || merchants[0] || null;

  return (
    <AuthContext.Provider
      value={{
        user,
        merchants,
        activeMerchant,
        isLoading,
        error,
        setActiveMerchantId,
        refreshAuth,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
