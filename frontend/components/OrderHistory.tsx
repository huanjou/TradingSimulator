'use client';
import React, { useEffect, useState, useMemo } from 'react';
import api from '@/lib/axios';
import { format } from 'date-fns';

import { useMarketStore } from '@/store/useMarketStore';

interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  order_type: string;
  quantity: number;
  price: number | null;
  average_fill_price?: number;
  status: string;
  created_at: string;
}

interface Trade {
  id: string;
  order_id: string;
  symbol: string;
  price: number;
  quantity: number;
  timestamp: string;
}

type TabType = 'open' | 'history' | 'trades';

export default function OrderHistory() {
  const refreshTrigger = useMarketStore((s) => s.orderRefreshTrigger);
  const [orders, setOrders] = useState<Order[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('trades');
  const [prices, setPrices] = useState<Record<string, number>>({});

  const newOrderPayload = useMarketStore((s) => s.newOrderPayload);

  const wsUpdatesRef = React.useRef<Record<string, any>>({});
  const wsTradesRef = React.useRef<Record<string, Trade>>({});

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ordersRes, tradesRes] = await Promise.all([
        api.get('/api/v1/orders/user/me?limit=50'),
        api.get('/api/v1/orders/user/me/trades?limit=50'),
      ]);

      const mergedOrders = ordersRes.data.map((o: Order) => {
        const update = wsUpdatesRef.current[o.id];
        if (update) {
          return {
            ...o,
            status: update.status,
            average_fill_price:
              update.average_fill_price != null
                ? parseFloat(update.average_fill_price)
                : o.average_fill_price,
          };
        }
        return o;
      });

      // Preserve optimistic order if DB replica hasn't caught up yet
      const currentNewOrder = useMarketStore.getState().newOrderPayload;
      if (currentNewOrder && !mergedOrders.some((o: Order) => o.id === currentNewOrder.id)) {
        const update = wsUpdatesRef.current[currentNewOrder.id];
        const optimisticOrder = update
          ? {
              ...currentNewOrder,
              status: update.status,
              average_fill_price:
                update.average_fill_price != null
                  ? parseFloat(update.average_fill_price)
                  : currentNewOrder.average_fill_price,
            }
          : currentNewOrder;
        mergedOrders.unshift(optimisticOrder);
      }

      // Merge DB trades with WS trades
      const dbTrades = tradesRes.data;
      const dbTradeIds = new Set(dbTrades.map((t: Trade) => t.id));
      const wsTradesList = Object.values(wsTradesRef.current).filter(
        (t: Trade) => !dbTradeIds.has(t.id),
      );

      const mergedTrades = [...wsTradesList, ...dbTrades].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      );

      setOrders(mergedOrders);
      setTrades(mergedTrades);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [refreshTrigger]);

  // Merge optimistic orders immediately when placed
  useEffect(() => {
    if (newOrderPayload) {
      setOrders((prev) => {
        if (!prev.some((o) => o.id === newOrderPayload.id)) {
          return [newOrderPayload, ...prev];
        }
        return prev;
      });
    }
  }, [newOrderPayload]);

  // Subscribe to private user events (WebSocket)
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;

    const connectWS = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${protocol}//${window.location.host}/ws/notifications`);

      ws.onopen = () => {
        console.log('[WS] Connected to notifications');
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };

      ws.onclose = (event) => {
        console.log('[WS] Closed:', event.code, event.reason);
        // Attempt to reconnect after 3 seconds
        reconnectTimer = setTimeout(connectWS, 3000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          console.log('[WS] Received:', msg.event, msg.data);

          if (msg.event === 'order_update') {
            const update = msg.data;
            const orderId = update.order_id;

            // Store the latest WS update in ref to prevent fetchData from overwriting it with stale DB data
            wsUpdatesRef.current[orderId] = update;

            setOrders((prevOrders) => {
              return prevOrders.map((o) => {
                if (o.id === orderId) {
                  return {
                    ...o,
                    status: update.status,
                    average_fill_price:
                      update.average_fill_price != null
                        ? parseFloat(update.average_fill_price)
                        : o.average_fill_price,
                  };
                }
                return o;
              });
            });
          } else if (msg.event === 'trade') {
            const newTrade = msg.data;
            const parsedTrade = {
              ...newTrade,
              price: parseFloat(newTrade.price),
              quantity: parseFloat(newTrade.quantity),
              timestamp:
                typeof newTrade.timestamp === 'number'
                  ? new Date(newTrade.timestamp * 1000).toISOString()
                  : newTrade.timestamp,
            };

            // Store the latest WS trade in ref to prevent fetchData from overwriting it
            wsTradesRef.current[parsedTrade.id] = parsedTrade;

            setTrades((prevTrades) => {
              if (prevTrades.some((t) => t.id === parsedTrade.id)) return prevTrades;
              return [parsedTrade, ...prevTrades];
            });
          }
        } catch (err) {
          console.error('Failed to parse websocket message', err);
        }
      };
    };

    connectWS();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) {
        ws.onclose = null; // prevent reconnect
        ws.close();
      }
    };
  }, []);

  // Subscribe to SSE for all unique symbols in trades
  useEffect(() => {
    if (trades.length === 0) return;

    const uniqueSymbols = Array.from(new Set(trades.map((t) => t.symbol)));
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
  }, [trades]);

  const displayedOrders = useMemo(() => {
    if (activeTab === 'open') {
      return orders.filter((o) => o.status === 'PENDING');
    } else if (activeTab === 'history') {
      return orders.filter((o) => o.status !== 'PENDING');
    }
    return [];
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

  const calculateTradePnL = (trade: Trade) => {
    const currentPrice = prices[trade.symbol];
    if (!currentPrice) return null;

    // Join with order to get side
    const order = orders.find((o) => o.id === trade.order_id);
    if (!order) return null;

    const diff = order.side === 'BUY' ? currentPrice - trade.price : trade.price - currentPrice;
    return diff * trade.quantity;
  };

  return (
    <div className="h-full flex flex-col p-4">
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
      </div>

      <div className="flex-1 overflow-auto pr-2">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-zinc-500 uppercase sticky top-0 bg-zinc-900 z-10">
            <tr>
              <th className="py-3 px-2 font-medium">Time</th>
              <th className="py-3 px-2 font-medium">Pair</th>
              {activeTab !== 'trades' && <th className="py-3 px-2 font-medium">Type</th>}
              {activeTab === 'trades' && <th className="py-3 px-2 font-medium">Side</th>}
              <th className="py-3 px-2 font-medium text-right">
                {activeTab === 'trades' ? 'Price' : 'Req. Price'}
              </th>
              {activeTab !== 'trades' && (
                <th className="py-3 px-2 font-medium text-right">Exec. Price</th>
              )}
              <th className="py-3 px-2 font-medium text-right">Amount</th>
              {activeTab === 'trades' ? (
                <th className="py-3 px-2 font-medium text-right">PnL</th>
              ) : (
                <th className="py-3 px-2 font-medium text-right">Status</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {activeTab === 'trades' ? (
              trades.length === 0 && !loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-zinc-500">
                    No trades found
                  </td>
                </tr>
              ) : (
                trades.map((trade) => {
                  const pnl = calculateTradePnL(trade);
                  const order = orders.find((o) => o.id === trade.order_id);
                  const side = order ? order.side : '-';

                  return (
                    <tr key={trade.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="py-3 px-2 text-zinc-400 whitespace-nowrap">
                        {trade.timestamp
                          ? format(new Date(trade.timestamp), 'HH:mm:ss')
                          : '--:--:--'}
                      </td>
                      <td className="py-3 px-2 text-zinc-200 font-medium">{trade.symbol}</td>
                      <td
                        className={`py-3 px-2 font-semibold ${
                          side === 'BUY'
                            ? 'text-emerald-500'
                            : side === 'SELL'
                              ? 'text-rose-500'
                              : 'text-zinc-500'
                        }`}
                      >
                        {side}
                      </td>
                      <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                        ${trade.price.toFixed(2)}
                      </td>
                      <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                        {trade.quantity}
                      </td>
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
                    </tr>
                  );
                })
              )
            ) : displayedOrders.length === 0 && !loading ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-zinc-500">
                  No orders found
                </td>
              </tr>
            ) : (
              displayedOrders.map((order) => (
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
                  <td className="py-3 px-2 text-zinc-400 text-right font-mono">
                    {order.average_fill_price ? `$${order.average_fill_price.toFixed(2)}` : '--'}
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
