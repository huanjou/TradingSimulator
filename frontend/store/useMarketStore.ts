import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface MarketState {
  symbol: string;
  orderRefreshTrigger: number;
  currentPrice: number | null;
  _hasHydrated: boolean;
  setSymbol: (symbol: string) => void;
  refreshOrders: () => void;
  setCurrentPrice: (price: number | null) => void;
  setHasHydrated: (state: boolean) => void;
  newOrderPayload: any | null;
  setNewOrderPayload: (order: any) => void;
  layoutResetTrigger: number;
  triggerLayoutReset: () => void;
}

export const useMarketStore = create<MarketState>()(
  persist(
    (set) => ({
      symbol: 'BTC/USD',
      orderRefreshTrigger: 0,
      currentPrice: null,
      _hasHydrated: false,
      newOrderPayload: null,
      layoutResetTrigger: 0,
      setSymbol: (symbol) => set({ symbol, currentPrice: null }),
      refreshOrders: () => set((state) => ({ orderRefreshTrigger: state.orderRefreshTrigger + 1 })),
      setCurrentPrice: (price) => set({ currentPrice: price }),
      setHasHydrated: (state) => set({ _hasHydrated: state }),
      setNewOrderPayload: (order) => set({ newOrderPayload: order }),
      triggerLayoutReset: () =>
        set((state) => ({ layoutResetTrigger: state.layoutResetTrigger + 1 })),
    }),
    {
      name: 'market-store',
      partialize: (state) => ({ symbol: state.symbol }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    },
  ),
);
