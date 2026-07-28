'use client';
import React, { useEffect, useState, useMemo } from 'react';
import api from '@/lib/axios';
import { format } from 'date-fns';

import { useMarketStore } from '@/store/useMarketStore';
import { useWalletStore } from '@/store/useWalletStore';

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

type TabType = 'open' | 'history' | 'positions';

export default function OrderHistory() {
  const refreshTrigger = useMarketStore((s) => s.orderRefreshTrigger);
  const [orders, setOrders] = useState<Order[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('positions');
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
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout;
    // React 18 StrictMode double-mounts effects in dev, so the first socket can
    // still be CONNECTING when cleanup runs. Track teardown to avoid closing a
    // connecting socket (which logs "closed before the connection is
    // established") and to suppress the spurious error/reconnect that follows.
    let isTeardown = false;

    const connectWS = () => {
      if (isTeardown) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${protocol}//${window.location.host}/ws/notifications`);

      ws.onopen = () => {
        // If the effect was torn down while still connecting, close cleanly now.
        if (isTeardown) {
          ws?.close();
          return;
        }
        console.log('[WS] Connected to notifications');
      };

      ws.onerror = (err) => {
        if (isTeardown) return;
        console.error('[WS] Error:', err);
      };

      ws.onclose = (event) => {
        if (isTeardown) return;
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
              const merged = [parsedTrade, ...prevTrades];
              return merged.sort(
                (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
              );
            });
          } else if (msg.event === 'balance_update') {
            const update = msg.data;
            useWalletStore.setState((state) => ({
              wallets: {
                ...state.wallets,
                [update.currency]: {
                  currency: update.currency,
                  available: String(update.available),
                  locked: String(update.locked),
                },
              },
            }));
          }
        } catch (err) {
          console.error('Failed to parse websocket message', err);
        }
      };
    };

    connectWS();

    return () => {
      isTeardown = true;
      clearTimeout(reconnectTimer);
      if (ws) {
        ws.onclose = null; // prevent reconnect
        ws.onerror = null; // suppress the spurious error from a mid-connect close
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
        // If still CONNECTING, the onopen handler above closes it once ready
        // (guarded by isTeardown), avoiding a close-before-established error.
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

  const positions = useMemo(() => {
    const posMap: Record<string, { quantity: number; totalCost: number }> = {};

    // Sort oldest to newest to replay trades
    const sortedTrades = [...trades].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    );

    sortedTrades.forEach((trade) => {
      const order = orders.find((o) => o.id === trade.order_id);
      const side = order ? order.side : '-';

      if (side === '-') return;

      if (!posMap[trade.symbol]) {
        posMap[trade.symbol] = { quantity: 0, totalCost: 0 };
      }

      const pos = posMap[trade.symbol];
      if (side === 'BUY') {
        pos.quantity += trade.quantity;
        pos.totalCost += trade.price * trade.quantity;
      } else if (side === 'SELL') {
        if (pos.quantity > 0) {
          const avgPrice = pos.totalCost / pos.quantity;
          pos.quantity -= trade.quantity;
          pos.totalCost -= avgPrice * trade.quantity;

          if (pos.quantity < 0.000001) {
            pos.quantity = 0;
            pos.totalCost = 0;
          }
        }
      }
    });

    return Object.entries(posMap)
      .filter(([_, pos]) => pos.quantity > 0)
      .map(([symbol, pos]) => ({
        symbol,
        quantity: pos.quantity,
        avgPrice: pos.totalCost / pos.quantity,
      }));
  }, [trades, orders]);

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

  return (
    <div className="h-full flex flex-col p-4">
      <div className="flex justify-between items-center mb-4 border-b border-zinc-800 pb-2">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab('positions')}
            className={`font-semibold text-sm pb-2 -mb-2.5 border-b-2 transition-colors ${
              activeTab === 'positions'
                ? 'text-zinc-100 border-emerald-500'
                : 'text-zinc-500 border-transparent hover:text-zinc-300'
            }`}
          >
            Positions
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
              {activeTab !== 'positions' && <th className="py-3 px-2 font-medium">Time</th>}
              <th className="py-3 px-2 font-medium">Pair</th>
              {activeTab !== 'positions' && <th className="py-3 px-2 font-medium">Type</th>}
              <th className="py-3 px-2 font-medium text-right">
                {activeTab === 'positions' ? 'Avg Price' : 'Req. Price'}
              </th>
              {activeTab === 'positions' && (
                <th className="py-3 px-2 font-medium text-right">Cur Price</th>
              )}
              {activeTab !== 'positions' && (
                <th className="py-3 px-2 font-medium text-right">Exec. Price</th>
              )}
              <th className="py-3 px-2 font-medium text-right">Amount</th>
              {activeTab === 'positions' ? (
                <th className="py-3 px-2 font-medium text-right">PnL</th>
              ) : (
                <th className="py-3 px-2 font-medium text-right">Status</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {activeTab === 'positions' ? (
              positions.length === 0 && !loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-zinc-500">
                    No open positions
                  </td>
                </tr>
              ) : (
                positions.map((pos) => {
                  const currentPrice = prices[pos.symbol];
                  let pnl: number | null = null;
                  if (currentPrice) {
                    pnl = (currentPrice - pos.avgPrice) * pos.quantity;
                  }

                  return (
                    <tr key={pos.symbol} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="py-3 px-2 text-zinc-200 font-medium">{pos.symbol}</td>
                      <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                        ${pos.avgPrice.toFixed(2)}
                      </td>
                      <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                        {currentPrice ? `$${currentPrice.toFixed(2)}` : '--'}
                      </td>
                      <td className="py-3 px-2 text-zinc-300 text-right font-mono">
                        {parseFloat(pos.quantity.toFixed(6))}
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
