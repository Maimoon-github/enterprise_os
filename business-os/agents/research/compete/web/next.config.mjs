/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow an isolated build dir (e.g. for verifying a prod build while a dev
  // server keeps using .next). Defaults to .next.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Proxy API calls to the FastAPI backend in dev so the browser hits same-origin.
  async rewrites() {
    const api = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
