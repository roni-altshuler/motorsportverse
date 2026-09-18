'use client';

import { useState } from 'react';
import type { RaceEvent, RaceContender } from '@/lib/race-centre';

const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;

/** Compare marginal probabilities; these are not head-to-head finishing odds. */
export function ForecastExplorer({ event }: { event: RaceEvent }) {
  const [market, setMarket] = useState<'win' | 'podium'>('win');
  const [fullField, setFullField] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [leftCode, setLeftCode] = useState(event.contenders[0]?.code ?? '');
  const [rightCode, setRightCode] = useState(event.contenders[1]?.code ?? '');
  const sorted = [...event.contenders].sort((a, b) => (b[market] ?? -1) - (a[market] ?? -1));
  const favourite = [...event.contenders].sort((a, b) => b.win - a.win)[0];
  const left = event.contenders.find(d => d.code === leftCode)!;
  const right = event.contenders.find(d => d.code === rightCode)!;
  const hasPodium = event.contenders.every(d => d.podium !== null);
  const shown = fullField ? sorted : sorted.slice(0, 5);
  return <div className="forecast-explorer">
    {favourite && <div className="field-outlook">
      <p className="mono-label">The shape of this race</p>
      <div className="field-outlook-heading"><strong>{favourite.name}</strong><b>{percent(favourite.win)}</b></div>
      <div className="field-distribution" aria-hidden><span style={{ width: `${favourite.win * 100}%`, background: event.accent }} /></div>
      <p>Rest of the field <span>{percent(Math.max(0, 1 - favourite.win))}</span></p>
      <small>The favourite’s win chance. The field is everyone else combined.</small>
    </div>}
    <div className="forecast-title"><span className="mono-label">{event.session} probabilities</span>
      <div className="race-view-switch compact" aria-label="Forecast market">{(['win', 'podium'] as const).map(m =>
        <button key={m} type="button" disabled={m === 'podium' && !hasPodium} aria-pressed={market === m} onClick={() => setMarket(m)}>{m === 'win' ? 'Win' : 'Podium'}</button>)}</div></div>
    {!hasPodium && <p className="forecast-caption">A complete, consistent podium forecast is not available.</p>}
    <ol className="contender-list">{shown.map((driver, i) => <li key={driver.code}>
      <span className="contender-rank">{String(i + 1).padStart(2, '0')}</span>
      <div className="contender-info"><div><strong>{driver.name}</strong><span>{percent(driver[market])}</span></div>
        <small>{driver.team || driver.code}</small><div className="probability-track" aria-hidden><span style={{ width: `${(driver[market] ?? 0) * 100}%`, background: event.accent }} /></div></div>
    </li>)}</ol>
    <div className="forecast-actions">
      {sorted.length > 5 && <button type="button" className="btn-ghost" aria-expanded={fullField} onClick={() => setFullField(!fullField)}>{fullField ? 'Show top five' : `Explore all ${sorted.length} drivers`}</button>}
      {sorted.length > 1 && <button type="button" className="btn-ghost" aria-expanded={comparing} onClick={() => setComparing(!comparing)}>{comparing ? 'Close comparison' : 'Compare drivers'}</button>}
    </div>
    <p className="forecast-caption">{fullField ? 'Full field shown.' : `Top ${Math.min(5, sorted.length)} shown.`} {market === 'win' ? 'Win probabilities cover the full field.' : 'Each driver’s chance of a top-three finish.'} {event.calibrated ? 'Calibration applied.' : 'Calibration not confirmed.'}</p>
    {comparing && left && right && <section className="driver-comparison" aria-label="Driver comparison">
      <h4>Two drivers. One race.</h4>
      <div className="comparison-selects">{[
        { label: 'First driver', value: leftCode, other: rightCode, set: setLeftCode },
        { label: 'Second driver', value: rightCode, other: leftCode, set: setRightCode },
      ].map(choice => <label key={choice.label}>{choice.label}<select value={choice.value} onChange={e => choice.set(e.target.value)}>
        {event.contenders.filter(d => d.code !== choice.other).map(d => <option key={d.code} value={d.code}>{d.name}</option>)}
      </select></label>)}</div>
      <table><caption className="sr-only">Win and podium probabilities for {left.name} and {right.name}</caption>
        <thead><tr><th scope="col">Chance</th><th scope="col">{left.code}</th><th scope="col">{right.code}</th></tr></thead>
        <tbody>{(['win', 'podium'] as const).map(m => <tr key={m}><th scope="row">{m === 'win' ? 'Win' : 'Podium'}</th><td>{percent(left[m])}</td><td>{percent(right[m])}</td></tr>)}</tbody></table>
      <ComparisonNote left={left} right={right} />
      <p className="forecast-caption">These compare each driver’s chance in the whole field. Head-to-head finishing odds require a separate forecast.</p>
    </section>}
    <details className="probability-guide"><summary>How to read these chances</summary>
      <p>A 20% win chance means about 20 wins per 100 comparable races in the model. The other outcomes remain possible. Podium chances add up to three places across a complete field.</p>
      <p>Calibration uses past outcomes to adjust probability estimates. The evidence below shows how the model compares with a simple baseline.</p>
    </details>
  </div>;
}
function ComparisonNote({ left, right }: { left: RaceContender; right: RaceContender }) {
  const gap = Math.abs(left.win - right.win) * 100;
  return <p className="comparison-gap">{gap < .05 ? 'The model gives these drivers the same win chance at this precision.' : <><strong>{left.win > right.win ? left.name : right.name}</strong> has a <b>{gap.toFixed(1)} percentage-point</b> higher win chance.</>}</p>;
}
