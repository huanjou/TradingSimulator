'use client';
import React, { useEffect, useState, useMemo } from 'react';
import api from '@/lib/axios';
import { format } from 'date-fns';
import { RefreshCw } from 'lucide-react';

import { useMarketStore } from '@/store/useMarketStore';

interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  order_type: string;
  quantity: number;
  price: number | null;
  status: string;
  created_at: string;
}

type TabType = 'open' | 'history' | 'trades';

export default function OrderHistory() {
  const refreshTrigger = useMarketStore((s) => s.orderRefreshTrigger);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('trades');
  const [prices, setPrices] = useState<Record<string, number>>({});

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/orders/user/me?limit=50`);
      setOrders(response.data);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [refreshTrigger]);

  // Subscribe to SSE for all unique symbols in FILLED orders
  useEffect(() => {
    const completedOrders = orders.filter(
      (o) => o.status === 'FILLED' || o.status === 'PARTIALLY_FILLED',
    );
    if (completedOrders.length === 0) return;

    const uniqueSymbols = Array.from(new Set(completedOrders.map((o) => o.symbol)));
    const symbolString = uniqueSymbols.join(',');

    const eventSource = new EventSource(
      `/api/v1/stream?symbol=${encodeURIComponent(symbolString)}`,
    );

    eventSource.addEventListener('price', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.bid_price !== undefined) {
          const tradePrice = (data.bid_price + data.ask_price) / 2;
          setPrices((prev) => ({
            ...prev,
            [data.symbol]: parseFloat(tradePrice.toFixed(2)),
          }));
        }
      } catch (err) {
        console.error('Failed to parse price data', err);
      }
    });

    return () => {
      eventSource.close();
    };
  }, [orders]);

  const displayedOrders = useMemo(() => {
    if (activeTab === 'open') {
      return orders.filter((o) => o.status === 'PENDING');
    } else if (activeTab === 'history') {
      return orders.filter((o) => o.status !== 'PENDING');
    } else {
      return orders.filter((o) => o.status === 'FILLED' || o.status === 'PARTIALLY_FILLED');
    }
  }, [orders, activeTab]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'FILLED':
        return 'text-emerald-400';
      case 'PARTIALLY_FILLED':
        return 'text-emerald-300';
      case 'PENDING':
        return 'text-amber-400';
      case 'CANCELED':
        return 'text-zinc-500';
      case 'REJECTED':
        return 'text-rose-400';
      default:
        return 'text-zinc-400';
    }
  };

  const calculatePnL = (order: Order) => {
    if (!order.price) return null;
    const currentPrice = prices[order.symbol];
    if (!currentPrice) return null;

    const diff = order.side === 'BUY' ? currentPrice - order.price : order.price - currentPrice;
    return diff * order.quantity;
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4 border-b border-zinc-800 pb-2">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab('trades')}
            className={`font-semibold text-sm pb-2 -mb-2.5 border-b-2 transition-colors ${
              activeTab === 'trades'
                ? 'text-zinc-100 border-emerald-500'
                : 'text-zinc-500 border-transparent hover:text-zinc-300'
            }`}
          >
            Trades
          </button>
          <button
            onClick={() => setActiveTab('open')}
            className={`font-semibold text-sm pb-2 -mb-2.5 border-b-2 transition-colors ${
              activeTab === 'open'
                ? 'text-zinc-100 border-emerald-500'
                : 'text-zinc-500 border-transparent hover:text-zinc-300'
            }`}
          >
            Open Orders
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`font-semibold text-sm pb-2 -mb-2.5 border-b-2 transition-colors ${
              activeTab === 'history'
                ? 'text-zinc-100 border-emerald-500'
                : 'text-zinc-500 border-transparent hover:text-zinc-300'
            }`}
          >
            History
          </button>
        </div>
        <button
          onClick={fetchOrders}
          className="text-zinc-400 hover:text-zinc-100 transition-colors"
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex-1 overflow-auto pr-2">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-zinc-500 uppercase sticky top-0 bg-zinc-900 z-10">
            <tr>
              <th className="py-3 px-2 font-medium">Time</th>
              <th className="py-3 px-2 font-medium">Pair</th>
              <th className="py-3 px-2 font-medium">Type</th>
              <th className="py-3 px-2 font-medium text-right">Price</th>
              <th className="py-3 px-2 font-medium text-right">Amount</th>
              {activeTab === 'trades' ? (
                <th className="py-3 px-2 font-medium text-right">PnL</th>
              ) : (
                <th className="py-3 px-2 font-medium text-right">Status</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {displayedOrders.length === 0 && !loading ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-zinc-500">
                  No {activeTab} found
                </td>
              </tr>
            ) : (
              displayedOrders.map((order) => {
                const pnl = activeTab === 'trades' ? calculatePnL(order) : null;

                return (
                  <tr key={order.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="py-3 px-2 text-zinc-400 whitespace-nowrap">
                      {order.created_at
                        ? format(new Date(order.created_at), 'HH:mm:ss')
                        : '--:--:--'}
                    </td>
                    <td className="py-3 px-2 text-zinc-200 font-medium">{order.symbol}</td>
                    <td
                      className={`py-3 px-2 font-semibold ${
                        order.side === 'BUY' ? 'text-emerald-500' : 'text-rose-500'
                      }`}
                    >
                      {order.side}
                    </td>
                    <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                      {order.price ? `$${order.price.toFixed(2)}` : 'MKT'}
                    </td>
                    <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                      {order.quantity}
                    </td>

                    {activeTab === 'trades' ? (
                      <td
                        className={`py-3 px-2 text-right font-mono font-medium ${
                          pnl !== null
                            ? pnl >= 0
                              ? 'text-emerald-400'
                              : 'text-rose-400'
                            : 'text-zinc-500'
                        }`}
                      >
                        {pnl !== null ? `${pnl > 0 ? '+' : ''}$${pnl.toFixed(2)}` : '--'}
                      </td>
                    ) : (
                      <td
                        className={`py-3 px-2 text-right font-medium ${getStatusColor(
                          order.status,
                        )}`}
                      >
                        {order.status}
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
