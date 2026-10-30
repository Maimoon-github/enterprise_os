import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@marketing-os/contracts"],
};

export default nextConfig;
