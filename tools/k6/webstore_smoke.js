import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:5000";

export const options = {
  vus: 5,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<3000"],
  },
};

export default function () {
  const home = http.get(`${BASE}/api/public/home`);
  check(home, {
    "home 200": (r) => r.status === 200,
    "home json": (r) => (r.headers["Content-Type"] || "").includes("json"),
  });

  const etag = home.headers.Etag || home.headers.ETag;
  if (etag) {
    const cached = http.get(`${BASE}/api/public/home`, {
      headers: { "If-None-Match": etag },
    });
    check(cached, { "home 304": (r) => r.status === 304 });
  }

  const catalog = http.get(`${BASE}/api/catalog`);
  check(catalog, {
    "catalog 200": (r) => r.status === 200,
    "catalog cache header": (r) => !!r.headers["X-Catalog-Cache"],
  });

  sleep(1);
}
