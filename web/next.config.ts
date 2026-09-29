import type { NextConfig } from "next";

// The browser calls /api/*; Next.js forwards it to the Scrubby FastAPI backend,
// so the API needs no CORS configuration.
const apiUrl = process.env.SCRUBBY_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default nextConfig;
