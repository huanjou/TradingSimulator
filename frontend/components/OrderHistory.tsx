'use client';
import React, { useEffect, useState } from 'react';
import api from '@/lib/axios';
import { format } from 'date-fns';
import { RefreshCw } from 'lucide-react';

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

interface OrderHistoryProps {
  refreshTrigger: number;
}

export default function OrderHistory({ refreshTrigger }: OrderHistoryProps) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/api/v1/orders/user/me?limit=20`);
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-emerald-400';
      case 'PENDING':
        return 'text-amber-400';
      case 'CANCELLED':
        return 'text-zinc-500';
      case 'FAILED':
        return 'text-rose-400';
      default:
        return 'text-zinc-400';
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-zinc-100 font-semibold text-lg">Order History</h2>
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
              <th className="py-3 px-2 font-medium text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {orders.length === 0 && !loading ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-zinc-500">
                  No orders found
                </td>
              </tr>
            ) : (
              orders.map((order) => (
                <tr key={order.id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="py-3 px-2 text-zinc-400 whitespace-nowrap">
                    {order.created_at ? format(new Date(order.created_at), 'HH:mm:ss') : '--:--:--'}
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
                  <td className="py-3 px-2 text-zinc-300 text-right font-mono">{order.quantity}</td>
                  <td
                    className={`py-3 px-2 text-right font-medium ${getStatusColor(order.status)}`}
                  >
                    {order.status}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
