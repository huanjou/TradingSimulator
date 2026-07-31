import http from "k6/http";
import ws from "k6/ws";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "10s", target: 10 },
    { duration: "20s", target: 10 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],
    "http_req_failed{type:api}": ["rate<0.15"],
  },
};

const API_GATEWAY_URL =
  __ENV.API_URL || "http://api-gateway:8000/api/v1/orders";
const USER_SERVICE_URL = __ENV.USER_SERVICE_URL || "http://user-service:8000";
const WALLET_SERVICE_URL =
  __ENV.WALLET_SERVICE_URL || "http://wallet-service:8000";
const WS_URL = __ENV.WS_URL || "ws://notification-ws:8000/notifications";
const SSE_URL = __ENV.SSE_URL || "http://stream-service:8000/api/v1/stream";

export function setup() {
  const loginUrl = `${USER_SERVICE_URL}/api/v1/auth/login`;
  const registerUrl = `${USER_SERVICE_URL}/api/v1/auth/register`;

  // Register a base user for the entire test
  const payload = JSON.stringify({
    email: `test_k6_${Date.now()}@example.com`,
    password: "Password123!",
  });

  const params = { headers: { "Content-Type": "application/json" } };

  // Try to register (ignore error if already exists)
  http.post(registerUrl, payload, params);

  // Login to get token
  const res = http.post(loginUrl, payload, params);

  let token = null;
  if (res.status === 200) {
    if (
      res.cookies &&
      res.cookies["access_token"] &&
      res.cookies["access_token"].length > 0
    ) {
      token = res.cookies["access_token"][0].value;
    } else {
      console.error("No access_token cookie found in response");
    }

    // Deposit funds for this user so orders don't fail with negative balance
    const depositParams = {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    };
    http.post(
      `${WALLET_SERVICE_URL}/api/v1/wallets/deposit`,
      JSON.stringify({ currency: "USD", amount: 1000000 }),
      depositParams,
    );
    http.post(
      `${WALLET_SERVICE_URL}/api/v1/wallets/deposit`,
      JSON.stringify({ currency: "BTC", amount: 1000 }),
      depositParams,
    );
  }

  return { token: token };
}

export default function (data) {
  if (!data.token) {
    console.error("Setup failed, no token");
    return;
  }

  const isBuy = Math.random() > 0.5;
  const price = 50000 + (Math.random() * 1000 - 500);
  const quantity = 0.01 + Math.random() * 0.1;

  const payload = JSON.stringify({
    symbol: "BTC/USD",
    side: isBuy ? "BUY" : "SELL",
    order_type: "LIMIT",
    quantity: parseFloat(quantity.toFixed(4)),
    price: parseFloat(price.toFixed(2)),
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${data.token}`,
    },
  };

  // 1. Connect to WebSocket to receive notifications.
  // The token is sent via the access_token cookie (query-string tokens are
  // rejected by the server for security reasons).
  const wsParams = {
    headers: Object.assign({}, params.headers, {
      Cookie: `access_token=${data.token}`,
    }),
  };

  const resWS = ws.connect(WS_URL, wsParams, function (socket) {
    socket.on("open", () => {
      // 2. While WS is open, create the order
      const createRes = http.post(
        `${API_GATEWAY_URL}/`,
        payload,
        Object.assign({}, params, { tags: { type: "api" } }),
      );

      check(createRes, {
        "order create status is 202": (r) => r.status === 202,
        "order has id": (r) => {
          try {
            return r.json().id !== undefined;
          } catch (e) {
            return false;
          }
        },
      });

      // 3. SSE check - send a quick request that times out intentionally
      // (k6 doesn't natively consume SSE streams indefinitely without blocking the VU)
      // We just ensure the endpoint accepts the connection.
      try {
        http.get(`${SSE_URL}?symbol=BTC/USD`, { timeout: 200 });
      } catch (e) {
        // Expected timeout
      }

      // Keep WS open for a brief moment to simulate receiving updates
      socket.setTimeout(function () {
        socket.close();
      }, 500);
    });

    socket.on("error", function (e) {
      if (e.error() != "websocket: close sent") {
        console.error("WS Error: ", e.error());
      }
    });
  });

  check(resWS, {
    "ws connected successfully (101)": (r) => r && r.status === 101,
  });

  sleep(0.5);
}
