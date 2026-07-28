'use client';

import { useEffect, useRef, useState } from 'react';
import {
  createAuthStore,
  AuthStoreContext,
  AuthStoreType,
  useAuthStore,
  User,
} from '../store/useAuthStore';
import { setOnAuthFailure } from '../lib/axios';
import AuthScreen from './AuthScreen';

export default function AuthProvider({
  children,
  initialUser,
}: {
  children: React.ReactNode;
  initialUser: User | null;
}) {
  // 1. Create an isolated store instance per request/client
  const storeRef = useRef<AuthStoreType>();
  if (!storeRef.current) {
    storeRef.current = createAuthStore({
      user: initialUser,
      isAuthenticated: !!initialUser,
      isInitializing: false,
    });
  }

  // 2. When a token refresh fails, the session is over: clear auth state so
  // AuthGate falls back to the login screen.
  useEffect(() => {
    setOnAuthFailure(() => {
      storeRef.current?.setState({ user: null, isAuthenticated: false });
    });
    return () => setOnAuthFailure(null);
  }, []);

  return (
    <AuthStoreContext.Provider value={storeRef.current}>
      <AuthGate>{children}</AuthGate>
    </AuthStoreContext.Provider>
  );
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  return <>{children}</>;
}
