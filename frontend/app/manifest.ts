import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "HuntMe",
    short_name: "HuntMe",
    description: "Hide. Hunt. Prove it. Real-world multiplayer hide-and-seek.",
    start_url: "/",
    display: "standalone",
    background_color: "#080d19",
    theme_color: "#080d19",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
