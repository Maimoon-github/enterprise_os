import type { MetadataRoute } from "next";

/** The app is behind sign-in and has nothing for search engines. */
export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", disallow: "/" }] };
}
