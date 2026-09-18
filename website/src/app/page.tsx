import Link from 'next/link';
import { RaceCentre } from '@/components/landing/RaceCentre';
import { CoverageWall } from '@/components/landing/CoverageWall';
import { getProjects } from '@/lib/registry';
import { getRaceFeed } from '@/lib/race-feed';

export default function HomePage() {
  const projects = getProjects();
  const feed = getRaceFeed(projects);
  return <div>
    <section className="fan-hero shell">
      <div className="fan-hero-copy">
        <p className="eyebrow eyebrow-accent"><span className="hero-grid-mark" aria-hidden>▦</span> Motorsport × machine intelligence</p>
        <h1>Feel the race.<br /><span>See the possibilities.</span></h1>
        <p>One place for every racing obsession. Explore the grid and its possibilities.</p>
        <div className="fan-hero-actions"><a href="#race-centre" className="btn-accent">Find your next race <span aria-hidden>↓</span></a>
          <Link href="/projects" className="btn-ghost">Explore the series →</Link></div>
        <div className="fan-hero-footnote"><span>{projects.length} racing series</span><span>Real published forecasts</span><span>Open evidence</span></div>
      </div>
      <div className="fan-hero-art" aria-hidden="true">
        <div className="track-orbit track-orbit-one" /><div className="track-orbit track-orbit-two" /><div className="track-orbit track-orbit-three" />
        <div className="track-apex"><span>THE NEXT</span><strong>TURN</strong><span>IS A POSSIBILITY.</span></div>
        <span className="track-marker marker-one" /><span className="track-marker marker-two" />
        <span className="track-coordinate">PACE / PROBABILITY / POSSIBILITY</span>
      </div>
    </section>
    <RaceCentre feed={feed} />
    <section className="shell fan-coverage">
      <div className="race-centre-heading"><div><p className="eyebrow eyebrow-accent">Find your racing world</p><h2>Different machines. Same obsession.</h2></div>
        <Link className="text-[var(--accent-text)]" href="/projects">All series →</Link></div>
      <CoverageWall items={projects.map(p => ({ slug: p.slug, sport: p.sport, icon: p.icon, accent: p.accent || '#e7102f', maturity: p.maturity, website: p.website || undefined }))} />
    </section>
    <section className="shell fan-method"><div><p className="eyebrow">The evidence matters</p><h2>A prediction is a starting point.</h2></div>
      <div><p>See how each forecast compares with a baseline and the result on track.</p>
        <Link href="/docs" className="text-[var(--accent-text)]">Inside the models →</Link></div></section>
  </div>;
}
