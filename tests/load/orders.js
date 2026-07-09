import http from "k6/http";
import { check, sleep } from "k6";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

export const options = {
  stages: [
    { duration: "5s", target: 10 }, // Ramp up to 10 users
    { duration: "10s", target: 10 }, // Stay at 10 users for 10s
    { duration: "5s", target: 0 }, // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95% of requests must complete below 500ms
    http_req_failed: ["rate<0.15"], // Allow up to 15% failed requests due to 404s during retry polling
  },
};

const BASE_URL =
  __ENV.API_URL || "http://exchange_api_gateway:8000/api/v1/orders";

export default function () {
  const userId = uuidv4();
  const isBuy = Math.random() > 0.5;
  const price = 50000 + (Math.random() * 1000 - 500); // Random price around 50000
  const quantity = 0.01 + Math.random() * 0.1;

  const payload = JSON.stringify({
    user_id: userId,
    symbol: "BTC/USD",
    side: isBuy ? "BUY" : "SELL",
    order_type: "LIMIT",
    quantity: parseFloat(quantity.toFixed(4)),
    price: parseFloat(price.toFixed(2)),
  });

  const randomIp = `${Math.floor(Math.random() * 255)}.${Math.floor(
    Math.random() * 255,
  )}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`;

  const params = {
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For": randomIp,
    },
  };

  // 1. Create the order
  const createRes = http.post(`${BASE_URL}/`, payload, params);

  check(createRes, {
    "create status is 202": (r) => r.status === 202,
    "has order id": (r) => {
      try {
        return r.json().id !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  // If order was created successfully, let's try to query it
  if (createRes.status === 202) {
    const orderId = createRes.json().id;

    // 2. Get the order with retries (eventual consistency)
    let getRes;
    let found = false;
    for (let i = 0; i < 15; i++) {
      getRes = http.get(`${BASE_URL}/${orderId}`, params);
      if (getRes.status === 200) {
        found = true;
        break;
      }
      sleep(0.2); // wait 200ms before retrying
    }

    // Only check the final result
    if (getRes) {
      check(getRes, {
        "get status is 200": (r) => r.status === 200,
        "order matches": (r) => {
          try {
            return r.json().id === orderId;
          } catch (e) {
            return false;
          }
        },
      });
    }
  }

  sleep(0.2); // Pacing between iterations
}
