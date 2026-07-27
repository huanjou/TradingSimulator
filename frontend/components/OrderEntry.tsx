'use client';
import React, { useState } from 'react';
import api from '@/lib/axios';
import axios from 'axios';
import { useAuthStore } from '@/store/useAuthStore';
import { useMarketStore } from '@/store/useMarketStore';
import { useWalletStore } from '@/store/useWalletStore';
import { ArrowUpCircle, ArrowDownCircle, PlusCircle, X } from 'lucide-react';
import Decimal from 'decimal.js';

export default function OrderEntry() {
  const { user } = useAuthStore();
  const { symbol, refreshOrders, currentPrice, setCurrentPrice } = useMarketStore();
  const { wallets, fetchWallets } = useWalletStore();
  const [quantity, setQuantity] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [showDeposit, setShowDeposit] = useState(false);
  const [depositAmount, setDepositAmount] = useState('1000');
  const [depositCurrency, setDepositCurrency] = useState('USD');
  const [depositLoading, setDepositLoading] = useState(false);

  const baseCurrency = symbol.split('/')[0] || '';
  const quoteCurrency = symbol.split('/')[1] || 'USD';

  React.useEffect(() => {
    if (user?.id) {
      fetchWallets();
      const interval = setInterval(fetchWallets, 5000); // Polling for balance updates
      return () => clearInterval(interval);
    }
  }, [user?.id, fetchWallets]);

  React.useEffect(() => {
    setCurrentPrice(null);
    const url = `/api/v1/stream?symbol=${encodeURIComponent(symbol)}`;
    const sse = new EventSource(url);

    sse.addEventListener('price', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.symbol && data.bid_price !== undefined) {
          const tradePrice = (data.bid_price + data.ask_price) / 2;
          setCurrentPrice(tradePrice);
        }
      } catch (err) {
        console.error('Failed to parse SSE data', err);
      }
    });

    sse.onerror = (err) => {
      console.error('SSE error', err);
    };

    return () => sse.close();
  }, [symbol, setCurrentPrice]);

  const submitOrder = async (side: 'BUY' | 'SELL') => {
    let parsedQuantity: number;
    try {
      const dec = new Decimal(quantity);
      if (dec.lte(0)) {
        setError('Quantity must be greater than 0');
        return;
      }
      parsedQuantity = dec.toNumber();
    } catch (e) {
      setError('Invalid quantity');
      return;
    }

    if (!user?.id) {
      setError('User not authenticated');
      return;
    }

    const cost = parsedQuantity * (currentPrice || 0); // approximate cost for market order
    if (side === 'BUY') {
      const availableQuote = parseFloat(wallets[quoteCurrency]?.available || '0');
      if (availableQuote < cost) {
        setError(
          `Insufficient ${quoteCurrency} balance. Need ~${cost.toFixed(
            2,
          )}, have ${availableQuote.toFixed(2)}`,
        );
        return;
      }
    } else {
      const availableBase = parseFloat(wallets[baseCurrency]?.available || '0');
      if (availableBase < parsedQuantity) {
        setError(
          `Insufficient ${baseCurrency} balance. Need ${parsedQuantity}, have ${availableBase}`,
        );
        return;
      }
    }

    setError('');
    setLoading(true);

    try {
      const response = await api.post('/api/v1/orders/', {
        user_id: user.id,
        symbol,
        side,
        order_type: 'MARKET',
        quantity: parsedQuantity,
      });
      setQuantity('');
      useMarketStore.getState().setNewOrderPayload(response.data);
      refreshOrders(); // notify order history to refetch
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        if (Array.isArray(detail)) {
          // FastAPI validation error (list of objects)
          setError(detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join(', '));
        } else if (typeof detail === 'string') {
          setError(detail);
        } else {
          setError('Failed to submit order');
        }
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDeposit = async () => {
    if (!user?.id) return;
    setDepositLoading(true);
    try {
      await api.post('/api/v1/wallets/deposit', {
        currency: depositCurrency,
        amount: parseFloat(depositAmount),
      });
      setShowDeposit(false);
    } catch (err) {
      console.error(err);
    } finally {
      setDepositLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 h-full overflow-y-auto p-3 relative custom-scrollbar">
      <h2 className="text-zinc-100 font-semibold text-sm flex items-center justify-between">
        <span>Order Entry</span>
        <button
          onClick={() => setShowDeposit(true)}
          className="text-[10px] flex items-center gap-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-2 py-1 rounded transition-colors"
        >
          <PlusCircle className="w-3 h-3" />
          Deposit
        </button>
      </h2>
      <div className="flex items-center justify-between text-zinc-400 text-xs">
        <span>
          {baseCurrency}:{' '}
          <span className="font-mono text-zinc-200">
            {parseFloat(wallets[baseCurrency]?.available || '0').toFixed(4)}
          </span>
        </span>
        <span>
          {quoteCurrency}:{' '}
          <span className="font-mono text-zinc-200">
            {parseFloat(wallets[quoteCurrency]?.available || '0').toFixed(2)}
          </span>
        </span>
      </div>

      <div className="flex flex-col gap-1 mt-1">
        <label className="text-xs text-zinc-400">Symbol</label>
        <div className="bg-zinc-800 text-zinc-100 px-2 py-1.5 rounded-md font-mono text-xs cursor-not-allowed">
          {symbol}
        </div>
      </div>

      <div className="flex flex-col gap-1 mt-1">
        <label className="text-xs text-zinc-400">Quantity</label>
        <div className="flex bg-zinc-800 rounded-md overflow-hidden border border-zinc-700 focus-within:border-blue-500 transition-colors">
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="bg-transparent text-zinc-100 px-2 py-1.5 w-full outline-none font-mono text-xs placeholder:text-zinc-600"
            placeholder="0.00"
            min="0"
            step="0.01"
          />
          <span className="text-zinc-500 px-2 py-1.5 border-l border-zinc-700 text-xs font-semibold flex items-center justify-center bg-zinc-800/50">
            {symbol.split('/')[0] || symbol}
          </span>
        </div>
        {error && <span className="text-red-500 text-[10px]">{error}</span>}
      </div>

      <div className="grid grid-cols-2 gap-2 mt-auto pt-2">
        <button
          onClick={() => submitOrder('BUY')}
          disabled={loading}
          className="bg-emerald-600 hover:bg-emerald-500 text-white py-2 rounded-md font-semibold text-sm transition-colors flex items-center justify-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ArrowUpCircle className="w-4 h-4" />
          Buy {baseCurrency}
        </button>
        <button
          onClick={() => submitOrder('SELL')}
          disabled={loading}
          className="bg-rose-600 hover:bg-rose-500 text-white py-2 rounded-md font-semibold text-sm transition-colors flex items-center justify-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ArrowDownCircle className="w-4 h-4" />
          Sell {baseCurrency}
        </button>
      </div>

      {loading && (
        <div className="text-center text-zinc-500 text-[10px] animate-pulse">Processing...</div>
      )}

      {showDeposit && (
        <div className="absolute inset-0 bg-zinc-900/90 backdrop-blur-sm z-10 flex flex-col p-4 justify-center">
          <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700 shadow-xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-zinc-100 font-semibold">Quick Deposit</h3>
              <button
                onClick={() => setShowDeposit(false)}
                className="text-zinc-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Currency</label>
                <select
                  value={depositCurrency}
                  onChange={(e) => setDepositCurrency(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-zinc-100"
                  disabled
                >
                  <option value="USD">USD</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 mb-1 block">Amount</label>
                <input
                  type="number"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-zinc-100"
                />
              </div>
              <button
                onClick={handleDeposit}
                disabled={depositLoading}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded text-sm font-semibold transition-colors mt-2"
              >
                {depositLoading ? 'Processing...' : 'Confirm Deposit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
