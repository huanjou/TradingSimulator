'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import OrderEntry from '@/components/OrderEntry';
import OrderHistory from '@/components/OrderHistory';
import TradesFeed from '@/components/TradesFeed';
import AuthScreen from '@/components/AuthScreen';
import Navbar from '@/components/Navbar';
import { useAuthStore } from '@/store/useAuthStore';
import api from '@/lib/axios';

// Disable SSR for TradingView chart as it requires window object
const TVChart = dynamic(() => import('@/components/TVChart'), { ssr: false });

export default function Dashboard() {
  const { user, isAuthenticated, setUser, logout } = useAuthStore();
  const [symbol, setSymbol] = useState('BTC/USD');
  const [currentTrade, setCurrentTrade] = useState<{ price: number; timestamp: string } | null>(
    null,
  );
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isInitializing, setIsInitializing] = useState(true);

  // Check auth status on mount
  React.useEffect(() => {
    api
      .get('/api/v1/users/me')
      .then((res) => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setIsInitializing(false));
  }, [setUser]);

  if (isInitializing) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-emerald-500 animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  // TradingView uses different symbol format e.g., BINANCE:BTCUSD
  const tvSymbol = `BINANCE:${symbol.replace('/', '')}`;

  return (
    <div className="min-h-screen bg-black text-zinc-100 font-sans px-4 flex flex-col gap-4">
      {/* Header */}
      <Navbar currentSymbol={symbol} onSymbolSelect={setSymbol} />

      {/* Main Grid */}
      <div className="flex-1 grid grid-cols-12 gap-4 h-[calc(100vh-100px)]">
        {/* Left Column: Chart & Order History */}
        <div className="col-span-12 lg:col-span-9 flex flex-col gap-4">
          <div className="flex-1 min-h-[400px]">
            <TVChart symbol={symbol} theme="dark" currentTrade={currentTrade} />
          </div>

          <div className="h-64">
            <OrderHistory refreshTrigger={refreshTrigger} />
          </div>
        </div>

        {/* Right Column: Order Entry & Trades Feed */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4">
          <div className="shrink-0">
            <OrderEntry
              symbol={symbol}
              currentPrice={currentTrade?.price || null}
              onOrderSubmitted={() => setRefreshTrigger((prev) => prev + 1)}
            />
          </div>

          <div className="flex-1 overflow-hidden">
            <TradesFeed symbol={symbol} onTradeUpdate={(trade) => setCurrentTrade(trade)} />
          </div>
        </div>
      </div>
    </div>
  );
}
