import http from "k6/http";
import { check, sleep } from "k6";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

export const options = {
  scenarios: {
    constant_request_rate: {
      executor: "constant-arrival-rate",
      rate: 30, // 30 requests per second
      timeUnit: "1s", // 30 requests per second
      duration: "5s",
      preAllocatedVUs: 10,
      maxVUs: 50,
    },
  },
  thresholds: {
    // We send 30/s for 5 seconds (150 requests total).
    // The sliding window logs ALL attempts (even rejected ones) in Redis.
    // So the first 10 requests succeed, and the remaining 140 fail with 429
    // because the 1-second window is constantly kept full (>10) by the hammering.
    // Failure rate should be exactly 140/150 = 93.33%.
    http_req_failed: ["rate>0.90"],
    checks: ["rate>0.95"],
  },
};

const BASE_URL =
  __ENV.API_URL || "http://exchange_api_gateway:8000/api/v1/orders";

export default function () {
  const userId = uuidv4();
  const isBuy = Math.random() > 0.5;
  const price = 50000 + (Math.random() * 1000 - 500);
  const quantity = 0.01 + Math.random() * 0.1;

  const payload = JSON.stringify({
    user_id: userId,
    symbol: "BTC/USD",
    side: isBuy ? "BUY" : "SELL",
    order_type: "LIMIT",
    quantity: parseFloat(quantity.toFixed(4)),
    price: parseFloat(price.toFixed(2)),
  });

  // STATIC IP to trigger Rate Limiter
  const staticIp = "192.168.1.99";

  const params = {
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For": staticIp,
    },
  };

  const createRes = http.post(`${BASE_URL}/`, payload, params);

  check(createRes, {
    "status is 202 or 429": (r) => r.status === 202 || r.status === 429,
  });
}
