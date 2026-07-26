import { create } from 'zustand';
import api from '../lib/axios';

export interface Wallet {
  currency: string;
  available: string;
  locked: string;
}

export interface WalletState {
  wallets: Record<string, Wallet>;
  isLoading: boolean;
  error: string | null;
  fetchWallets: () => Promise<void>;
}

export const useWalletStore = create<WalletState>()((set) => ({
  wallets: {},
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
      set({ error: error?.response?.data?.detail || error.message || 'Failed to fetch wallets', isLoading: false });
    }
  },
}));
