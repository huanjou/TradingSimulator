import { createStore, useStore } from 'zustand';
import { createContext, useContext } from 'react';
import axios, { AxiosError } from 'axios';
import api from '../lib/axios';

export interface User {
  id: string;
  email: string;
}

export interface LoginCredentials {
  email: string;
  password?: string;
  [key: string]: any;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  error: string | null;

  checkAuth: () => Promise<void>;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export type AuthStoreType = ReturnType<typeof createAuthStore>;

export const createAuthStore = (initialProps?: Partial<AuthState>) => {
  return createStore<AuthState>()((set) => ({
    user: null,
    isAuthenticated: false,
    isInitializing: false,
    error: null,
    ...initialProps,

    clearError: () => set({ error: null }),

    checkAuth: async () => {
      set({ isInitializing: true });
      try {
        const response = await api.get('/api/v1/users/me');
        set({ user: response.data, isAuthenticated: true, isInitializing: false, error: null });
      } catch (error) {
        console.error('checkAuth failed:', error);
        set({ user: null, isAuthenticated: false, isInitializing: false });
      }
    },

    login: async (credentials) => {
      set({ error: null });
      try {
        await api.post('/api/v1/auth/login', credentials);
        // After login, fetch user info
        const response = await api.get('/api/v1/users/me');
        set({ user: response.data, isAuthenticated: true });
      } catch (error: unknown) {
        if (axios.isAxiosError(error)) {
          set({ error: error.response?.data?.detail || 'Login failed' });
        } else {
          set({ error: 'An unexpected error occurred during login' });
        }
        throw error;
      }
    },

    register: async (credentials) => {
      set({ error: null });
      try {
        await api.post('/api/v1/auth/register', credentials);
        // Immediately login after registration
        await api.post('/api/v1/auth/login', credentials);
        const response = await api.get('/api/v1/users/me');
        set({ user: response.data, isAuthenticated: true });
      } catch (error: unknown) {
        if (axios.isAxiosError(error)) {
          set({ error: error.response?.data?.detail || 'Registration failed' });
        } else {
          set({ error: 'An unexpected error occurred during registration' });
        }
        throw error;
      }
    },

    logout: async () => {
      try {
        await api.post('/api/v1/auth/logout');
      } catch (error) {
        console.error('Logout failed:', error);
      } finally {
        set({ user: null, isAuthenticated: false });
      }
    },
  }));
};

export const AuthStoreContext = createContext<AuthStoreType | null>(null);

export function useAuthStore(): AuthState;
export function useAuthStore<T>(selector: (state: AuthState) => T): T;
export function useAuthStore<T>(selector?: (state: AuthState) => T): T | AuthState {
  const store = useContext(AuthStoreContext);
  if (!store) {
    throw new Error('useAuthStore must be used within an AuthStoreContext.Provider');
  }
  // If selector is provided, use it, otherwise return the whole store
  return useStore(store, selector || ((state) => state as unknown as T));
}
