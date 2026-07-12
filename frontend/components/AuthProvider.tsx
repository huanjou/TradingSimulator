'use client';

import { useEffect, useRef } from 'react';
import { useAuthStore, User } from '../store/useAuthStore';
import AuthScreen from './AuthScreen';

export default function AuthProvider({
  children,
  initialUser,
}: {
  children: React.ReactNode;
  initialUser: User | null;
}) {
  const initialized = useRef(false);
  const { isAuthenticated } = useAuthStore();

  if (!initialized.current) {
    useAuthStore.setState({
      user: initialUser,
      isAuthenticated: !!initialUser,
      isInitializing: false,
    });
    initialized.current = true;
  }

  // We no longer render a spinner.
  // If not authenticated, we immediately show the AuthScreen.
  if (!isAuthenticated && !initialUser) {
    return <AuthScreen />;
  }

  return <>{children}</>;
}
