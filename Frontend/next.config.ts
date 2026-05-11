import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  sassOptions: {
    includePaths: [path.join(__dirname, "src/styles")],
    additionalData: `@use "vars" as *;`
  },
  webpack: (config) => {
    // On Windows, process.cwd() returns 'frontend' (lowercase) while fs.realpath()
    // returns 'Frontend' (the real filesystem name), causing webpack to load the same
    // module files twice under different IDs, which breaks React context.
    config.resolve.symlinks = false;
    return config;
  },
};

export default nextConfig;
