'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ForecastExplorer } from './ForecastExplorer';
import { displayDate, isStale, raceStatus, type RaceEvent, type RaceFeed } from '@/lib/race-centre';

const STORAGE = 'motorsportverse:favourite-series:v1';
const VERDICTS: Record<string, string> = {
  better: 'Beating the baseline', worse: 'Behind the baseline', inconclusive: 'No clear edge yet',
  insufficient: 'Building the evidence', unavailable: 'Not yet benchmarked',
};
const STATUS = { upcoming: 'Upcoming', completed: 'Results recorded', awaiting: 'Awaiting results', undated: 'Schedule pending' };

export function RaceCentre({ feed }: { feed: RaceFeed }) {
  const [today, setToday] = useState(feed.asOf);
  const [favourites, setFavourites] = useState<string[]>([]);
  const [series, setSeries] = useState('all');
  const [view, setView] = useState('upcoming');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [readyOnly, setReadyOnly] = useState(false);
  const [shareMessage, setShareMessage] = useState('');
  const [limit, setLimit] = useState(8);
  useEffect(() => {
    const update = () => setToday(new Date().toISOString().slice(0, 10));
    update();
    const openSharedRace = () => {
      const id = new URLSearchParams(window.location.search).get('race');
      const race = feed.events.find(e => e.id === id);
      if (race) {
        setSelectedId(race.id); setSeries(race.slug);
        setView(race.completed ? 'recent' : raceStatus(race, new Date().toISOString().slice(0, 10)) === 'upcoming' ? 'upcoming' : 'all');
        setLimit(8); setReadyOnly(false); setQuery('');
      }
    };
    openSharedRace();
    window.addEventListener('popstate', openSharedRace);
    const timer = window.setInterval(update, 60000);
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(STORAGE) ?? '[]');
      if (Array.isArray(saved)) setFavourites(saved.filter((s): s is string => typeof s === 'string' && feed.series.some(p => p.slug === s)));
    } catch { /* Privacy mode or invalid saved preferences must not block browsing. */ }
    return () => { window.clearInterval(timer); window.removeEventListener('popstate', openSharedRace); };
  }, [feed.series, feed.events]);
  function toggleFavourite(slug: string) {
    const next = favourites.includes(slug) ? favourites.filter(s => s !== slug) : [...favourites, slug];
    setFavourites(next);
    try { localStorage.setItem(STORAGE, JSON.stringify(next)); } catch { /* Session-only favourites. */ }
  }
  const filtered = useMemo(() => feed.events.filter(event => {
    const status = raceStatus(event, today);
    return (series === 'all' || series === 'favourites' && favourites.includes(event.slug) || series === event.slug)
      && (view === 'all' || view === 'upcoming' && status === 'upcoming' || view === 'recent' && status === 'completed')
      && (!readyOnly || status === 'upcoming' && event.contenders.length > 0)
      && `${event.name} ${event.sport} ${event.location}`.toLowerCase().includes(query.toLowerCase().trim());
  }).sort((a, b) => {
    const direction = view === 'recent' ? -1 : 1;
    return direction * (a.date ?? '9999').localeCompare(b.date ?? '9999') || a.round - b.round || a.sport.localeCompare(b.sport);
  }), [feed.events, series, view, query, today, favourites, readyOnly]);
  const selected = filtered.find(event => event.id === selectedId) ?? filtered[0];
  const visible = filtered.slice(0, limit);
  // Keep a directly linked race visible even outside the first calendar page.
  if (selected && !visible.some(event => event.id === selected.id)) visible.unshift(selected);
  const evidence = feed.series.find(s => s.slug === selected?.slug);
  const awaiting = feed.events.filter(e => raceStatus(e, today) === 'awaiting').length;
  const upcoming = feed.events.filter(e => raceStatus(e, today) === 'upcoming').length;
  const canShowForecast = selected && raceStatus(selected, today) === 'upcoming' && selected.contenders.length > 0;
  const ready = feed.events.filter(e => raceStatus(e, today) === 'upcoming' && e.contenders.length > 0).length;
  const weekEnd = new Date(`${today}T00:00:00Z`); weekEnd.setUTCDate(weekEnd.getUTCDate() + 7);
  const thisWeek = feed.events.filter(e => raceStatus(e, today) === 'upcoming' && e.date! < weekEnd.toISOString().slice(0, 10)).length;
  async function shareRace() {
    if (!selected) return;
    const url = new URL(window.location.href); url.searchParams.set('race', selected.id); url.hash = 'race-centre';
    try { await navigator.clipboard.writeText(url.toString()); setShareMessage('Race link copied.'); }
    catch { setShareMessage(url.toString()); }
  }

  return <section id="race-centre" className="race-centre shell" aria-labelledby="race-centre-title">
    <div className="race-centre-heading">
      <div><p className="eyebrow eyebrow-accent">The race centre</p><h2 id="race-centre-title">Your weekend. Across every grid.</h2>
        <p className="text-[var(--ink-muted)]">Find the next race, explore the probabilities, and follow the series you love.</p></div>
      <div className="race-count"><strong>{upcoming}</strong><span>scheduled races ahead</span></div>
    </div>
    <div className="race-pulse" aria-label="Calendar coverage">
      <div><b>{thisWeek}</b><span>races in the next 7 days</span></div>
      <div><b>{ready}</b><span>upcoming forecasts available</span></div>
      <div><b>{feed.series.length}</b><span>racing series to explore</span></div>
    </div>
    <div className="series-filters" aria-label="Filter by racing series">
      {[{ slug: 'all', sport: 'All series' }, { slug: 'favourites', sport: '★ Following' }, ...feed.series].map(s =>
        <button key={s.slug} type="button" aria-pressed={series === s.slug} className="race-chip"
          onClick={() => { setSeries(s.slug); setLimit(8); }}>{s.sport}</button>)}
    </div>
    <div className="race-toolbar">
      <div className="race-view-switch" aria-label="Race schedule view">
        {[['upcoming', 'Upcoming'], ['recent', 'Results'], ['all', 'Full calendar']].map(([key, label]) =>
          <button key={key} type="button" aria-pressed={view === key} onClick={() => { setView(key); setLimit(8); if (key !== 'upcoming') setReadyOnly(false); }}>{label}</button>)}
      </div>
      <label className="race-search"><span className="sr-only">Search races</span><span aria-hidden>⌕</span>
        <input type="search" placeholder="Find a race or circuit…" value={query} onChange={e => { setQuery(e.target.value); setLimit(8); }} /></label>
    </div>
    <div className="forecast-filter"><label><input type="checkbox" checked={readyOnly} onChange={e => { setReadyOnly(e.target.checked); if (e.target.checked) setView('upcoming'); setLimit(8); }} /> Forecasts ready</label><span>Only races with a published forecast</span></div>
    <div className="race-workspace">
      <div className="race-list">
        <p className="mono-label race-list-caption" aria-live="polite">{filtered.length} races · dates in UTC</p>
        {!filtered.length && <div className="race-empty"><h3>{series === 'favourites' && !favourites.length ? 'Build your own grid.' : 'No races in this view.'}</h3>
          <p>{series === 'favourites' && !favourites.length ? 'Choose a race, then follow its series to keep it here.' : 'Try another series, clear your search, or explore the full calendar.'}</p>
          <button className="btn-ghost" onClick={() => { setSeries('all'); setView('all'); setQuery(''); setReadyOnly(false); }}>Explore the calendar</button></div>}
        {visible.map(event => <button key={event.id} type="button" className="race-row"
          aria-pressed={selected?.id === event.id} onClick={() => { setSelectedId(event.id); setShareMessage(''); }}>
          <span className="race-date">{displayDate(event.date)}<small>R{String(event.round).padStart(2, '0')}</small></span>
          <span className="race-row-main"><span className="race-sport"><span className="race-series-dot" style={{ background: event.accent }} aria-hidden />{event.sport}</span>
            <strong>{event.name}</strong><span className="race-row-location">{event.location || `${event.season} season`}</span></span>
          <span className={`race-status race-status-${raceStatus(event, today)}`}>{STATUS[raceStatus(event, today)]}</span>
          <span className="race-row-arrow" aria-hidden>↗</span>
        </button>)}
        {filtered.length > limit && <button className="btn-ghost race-more" onClick={() => setLimit(n => n + 12)}>Show more races</button>}
      </div>
      <aside className="race-focus" aria-label="Selected race forecast">
        {selected ? <>
          <div className="race-focus-top"><span className="eyebrow" style={{ color: "var(--ink-muted)" }}><span className="race-series-dot" style={{ background: selected.accent }} aria-hidden />{selected.sport} · Round {selected.round}</span>
            <button type="button" className="follow-button" aria-pressed={favourites.includes(selected.slug)}
              aria-label={`${favourites.includes(selected.slug) ? 'Unfollow' : 'Follow'} ${selected.sport}`}
              onClick={() => toggleFavourite(selected.slug)}>{favourites.includes(selected.slug) ? '★ Following' : '☆ Follow'}</button></div>
          <h3>{selected.name}</h3><p className="text-[var(--ink-muted)]">{displayDate(selected.date)} · {selected.season}</p>
          <div className="race-share"><button type="button" onClick={shareRace}>Copy race link ↗</button><p role="status">{shareMessage}</p></div>
          {canShowForecast ? <ForecastExplorer key={selected.id} event={selected} /> : <div className="forecast-pending"><span aria-hidden>◎</span><h4>{selected.completed ? 'The result is in.' : raceStatus(selected, today) === 'awaiting' ? 'Waiting for the result.' : 'The forecast is still taking shape.'}</h4>
            <p>{selected.completed ? 'Open the series dashboard for classifications and the model’s race review.' : raceStatus(selected, today) === 'awaiting' ? 'The scheduled date has passed. A result has not been recorded in this feed.' : 'No verified race forecast is available here yet. Explore the series dashboard for more detail.'}</p></div>}
          {evidence && <div className="race-evidence"><p className="mono-label">Does the model have an edge?</p><strong>{VERDICTS[evidence.verdict] ?? VERDICTS.unavailable}</strong>
            {evidence.modelError !== null && evidence.baselineError !== null && <div className="evidence-values">
              <span><b>{evidence.modelError.toFixed(2)}</b>Model</span><span><b>{evidence.baselineError.toFixed(2)}</b>{evidence.baseline}</span></div>}
            <p>{evidence.rounds > 0 ? `Average position error · lower is better · ${evidence.rounds} paired rounds.` : evidence.note}</p>
            <details><summary>What this comparison means</summary><p>{evidence.note}</p></details></div>}
          <a className="btn-accent race-dashboard-link" href={selected.href}>Explore {selected.sport} <span aria-hidden>↗</span></a>
          <ForecastStamp event={selected} today={today} />
        </> : <div className="race-empty"><h3>A whole world of racing.</h3><p>Select a race to explore its forecast and the evidence behind it.</p></div>}
      </aside>
    </div>
    <div className="race-feed-note"><p>Published forecasts, not live timing. {awaiting > 0 && `${awaiting} scheduled races are awaiting recorded results.`}</p>
      <Link href="/docs">How the predictions work →</Link></div>
  </section>;
}
function ForecastStamp({ event, today }: { event: RaceEvent; today: string }) {
  const date = event.updatedAt?.slice(0, 10);
  return <p className="forecast-stamp">{date && !Number.isNaN(Date.parse(date)) ? `Data updated ${displayDate(date)} ${date.slice(0, 4)}.` : 'Update time unavailable.'}
    {isStale(event, today) && ' This snapshot may be out of date.'}</p>;
}
