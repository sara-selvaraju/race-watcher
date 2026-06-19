const DEFAULT_PROD_API = "https://api-production-f9fa.up.railway.app";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "production" ? DEFAULT_PROD_API : "http://localhost:8000");
