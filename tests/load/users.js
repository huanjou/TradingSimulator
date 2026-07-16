import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "10s", target: 50 }, // Ramp up to 50 users
    { duration: "30s", target: 50 }, // Stay at 50 users
    { duration: "10s", target: 0 }, // Ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<200"], // 95% of requests should be below 200ms
    http_req_failed: ["rate<0.01"], // Error rate should be less than 1%
  },
};

export function setup() {
  // Login once to get the auth token for the rest of the VUs (Virtual Users)
  // Or we can register a test user if it doesn't exist
  const loginUrl = "http://user-service:8000/api/v1/auth/login";
  const payload = JSON.stringify({
    email: "test_k6@example.com",
    password: "Password123!",
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  // Attempt to register first, ignore if exists
  http.post("http://user-service:8000/api/v1/auth/register", payload, params);

  const res = http.post(loginUrl, payload, params);

  // Extract token from response or cookies
  let token = null;
  if (res.status === 200) {
    token = res.json("access_token");
  }

  return { token: token };
}

export default function (data) {
  const url = "http://user-service:8000/api/v1/users/me";

  const params = {
    headers: {},
  };

  if (data.token) {
    params.headers["Authorization"] = `Bearer ${data.token}`;
  }

  const res = http.get(url, params);

  check(res, {
    "is status 200": (r) => r.status === 200,
  });

  sleep(0.1);
}
