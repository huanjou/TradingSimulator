import { create } from 'zustand';
import api from '../lib/axios';

export interface Wallet {
  currency: string;
  available: string;
  locked: string;
}

export interface WalletState {
  wallets: Record<string, Wallet>;
  // Latest balance_version returned by a deposit; sent with orders as
  // depends_on_balance_version so the engine applies the deposit first.
  balanceVersion: number | null;
  isLoading: boolean;
  error: string | null;
  fetchWallets: () => Promise<void>;
  setBalanceVersion: (version: number) => void;
}

export const useWalletStore = create<WalletState>()((set) => ({
  wallets: {},
  balanceVersion: null,
  isLoading: false,
  error: null,
  fetchWallets: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/api/v1/wallets/me');
      const walletsArr = response.data.balances || [];
      const walletsMap: Record<string, Wallet> = {};
      for (const w of walletsArr) {
        walletsMap[w.currency] = w;
      }
      set({ wallets: walletsMap, isLoading: false });
    } catch (error: any) {
      set({
        error: error?.response?.data?.detail || error.message || 'Failed to fetch wallets',
        isLoading: false,
      });
    }
  },
  setBalanceVersion: (version: number) => {
    set((state) => ({
      balanceVersion: Math.max(state.balanceVersion ?? 0, version),
    }));
  },
}));
