'use client';
import React, { useState, useEffect } from 'react';
import api from '@/lib/axios';
import { useAuthStore } from '@/store/useAuthStore';
import { ArrowUpCircle, ArrowDownCircle } from 'lucide-react';

interface OrderEntryProps {
  symbol: string;
  currentPrice: number | null;
  onOrderSubmitted?: () => void;
}

export default function OrderEntry({ symbol, currentPrice, onOrderSubmitted }: OrderEntryProps) {
  const { user } = useAuthStore();
  const [quantity, setQuantity] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submitOrder = async (side: 'BUY' | 'SELL') => {
    if (!quantity || isNaN(Number(quantity)) || Number(quantity) <= 0) {
      setError('Invalid quantity');
      return;
    }
    if (!user?.id) {
      setError('User not authenticated');
      return;
    }
    setError('');
    setLoading(true);

    try {
      await api.post('/api/v1/orders/', {
        user_id: user.id,
        symbol,
        side,
        order_type: 'MARKET',
        quantity: Number(quantity),
      });
      setQuantity('');
      if (onOrderSubmitted) onOrderSubmitted();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        // FastAPI validation error (list of objects)
        setError(detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join(', '));
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError('Failed to submit order');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex flex-col gap-4">
      <h2 className="text-zinc-100 font-semibold text-lg flex items-center justify-between">
        <span>Order Entry</span>
        {currentPrice && (
          <span className="text-zinc-400 text-sm font-mono">${currentPrice.toFixed(2)}</span>
        )}
      </h2>

      <div className="flex flex-col gap-2">
        <label className="text-sm text-zinc-400">Symbol</label>
        <div className="bg-zinc-800 text-zinc-100 px-3 py-2 rounded-md font-mono text-sm cursor-not-allowed">
          {symbol}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-sm text-zinc-400">Quantity</label>
        <div className="flex bg-zinc-800 rounded-md overflow-hidden border border-zinc-700 focus-within:border-blue-500 transition-colors">
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="bg-transparent text-zinc-100 px-3 py-2 w-full outline-none font-mono text-sm placeholder:text-zinc-600"
            placeholder="0.00"
            min="0"
            step="0.01"
          />
          <span className="text-zinc-500 px-3 py-2 border-l border-zinc-700 text-sm font-semibold flex items-center justify-center bg-zinc-800/50">
            {symbol.split('/')[0] || symbol}
          </span>
        </div>
        {error && <span className="text-red-500 text-xs">{error}</span>}
      </div>

      <div className="grid grid-cols-2 gap-3 mt-4">
        <button
          onClick={() => submitOrder('BUY')}
          disabled={loading}
          className="bg-emerald-600 hover:bg-emerald-500 text-white py-3 rounded-md font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ArrowUpCircle className="w-5 h-5" />
          Buy / Long
        </button>
        <button
          onClick={() => submitOrder('SELL')}
          disabled={loading}
          className="bg-rose-600 hover:bg-rose-500 text-white py-3 rounded-md font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ArrowDownCircle className="w-5 h-5" />
          Sell / Short
        </button>
      </div>

      {loading && (
        <div className="text-center text-zinc-500 text-xs animate-pulse">Processing...</div>
      )}
    </div>
  );
}
