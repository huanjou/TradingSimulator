'use client';

import { useEffect, useRef } from 'react';
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
      // SSR may fail with an expired access token even though the session is
      // still refreshable client-side, so stay in the initializing state
      // until checkAuth() below resolves.
      isInitializing: !initialUser,
    });
  }

  // If SSR could not authenticate (e.g. expired access token), attempt a
  // client-side checkAuth(): the axios 401 interceptor will hit /auth/refresh
  // (the refresh cookie is path-scoped to that endpoint) and retry.
  useEffect(() => {
    if (!initialUser) {
      storeRef.current?.getState().checkAuth();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
  const isInitializing = useAuthStore((s) => s.isInitializing);

  // While the client-side refresh attempt is in flight, render nothing to
  // avoid flashing the login screen for still-valid sessions.
  if (isInitializing) {
    return null;
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  return <>{children}</>;
}
