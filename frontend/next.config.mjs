/** API calls go through a same-origin proxy so the httpOnly session cookie works without CORS tricks. */
const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";
export default {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
  // Open the app straight on the login page (landing page file is left untouched).
  async redirects() {
    return [{ source: "/", destination: "/login", permanent: false }];
  },
  async headers() {
    return [{ source: "/(.*)", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "Permissions-Policy", value: "microphone=(self), camera=(self), geolocation=(self)" },
    ]}];
  },
};