import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal, self-contained server.js output for Docker -- see web/Dockerfile.
  output: "standalone",
};

export default nextConfig;
