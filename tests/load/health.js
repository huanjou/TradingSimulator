import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "5s", target: 20 }, // увеличиваем на 20 пользователей каждые 5 сек
    { duration: "10s", target: 20 }, // останавливаем на 20 пользователях в течении 10 сек
    { duration: "5s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<200"], // 95% должны пройти быстрее 200ms
    http_req_failed: ["rate<0.01"], // ошибки меньше 1%
  },
};

export default function () {
  const url = "http://api-gateway:8000/api/v1/health/";

  const res = http.get(url);

  check(res, {
    "is status 200": (r) => r.status === 200,
    "db is connected": (r) => {
      try {
        return r.json().db === "connected";
      } catch (e) {
        return false;
      }
    },
    "kafka is connected": (r) => {
      try {
        return r.json().kafka === "connected";
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.1); // Short pause between iterations to simulate realistic behavior
}
