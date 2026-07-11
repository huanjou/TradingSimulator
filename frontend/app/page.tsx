'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import OrderEntry from '@/components/OrderEntry';
import OrderHistory from '@/components/OrderHistory';
import TradesFeed from '@/components/TradesFeed';
import AuthScreen from '@/components/AuthScreen';
import { Activity, LogOut } from 'lucide-react';
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
    api.get('/api/v1/users/me')
      .then(res => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setIsInitializing(false));
  }, [setUser]);

  if (isInitializing) {
    return <div className="min-h-screen bg-black flex items-center justify-center"><div className="text-emerald-500 animate-pulse">Loading...</div></div>;
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  // TradingView uses different symbol format e.g., BINANCE:BTCUSD
  const tvSymbol = `BINANCE:${symbol.replace('/', '')}`;

  return (
    <div className="min-h-screen bg-black text-zinc-100 font-sans p-4 flex flex-col gap-4">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-6 h-6 text-emerald-500" />
          <h1 className="text-xl font-bold tracking-tight">Antigravity Exchange</h1>
          <span className="bg-zinc-800 text-zinc-400 text-xs px-2 py-1 rounded ml-2 hidden md:inline-block">
            {user?.email}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex gap-2">
          {['BTC/USD', 'ETH/USD', 'SOL/USD'].map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                symbol === s
                  ? 'bg-zinc-800 text-white border border-zinc-700'
                  : 'bg-zinc-900 text-zinc-400 hover:text-white border border-transparent'
              }`}
            >
              {s}
            </button>
          ))}
          </div>
          
          <button 
            onClick={async () => {
              await api.post('/api/v1/auth/logout');
              logout();
            }}
            className="p-2 text-zinc-400 hover:text-white bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 rounded-md transition-colors"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

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
