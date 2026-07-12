'use client';

import { useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isInitializing, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return <>{children}</>;
}
