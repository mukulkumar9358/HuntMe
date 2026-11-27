import { Hero } from "@/components/landing/Hero";
import { Features, HowToPlay, RecentMatches, Safety, SiteFooter } from "@/components/landing/Sections";

export default function Home() {
  return (
    <>
      <Hero />
      <RecentMatches />
      <HowToPlay />
      <Features />
      <Safety />
      <SiteFooter />
    </>
  );
}
