import React, { useState } from 'react';
import { Bike, Briefcase, Car, CircleAlert, Footprints, Info, LoaderCircle, Motorbike, Navigation, RefreshCw, Route, TrafficCone } from 'lucide-react';
import { useCommute } from '@/hooks/useCommute';
import { formatKm, formatMinutes } from '@/lib/mapApi';
import type { CommuteCardProps, RouteOption, RouteSelection, RouteTag, TravelMode } from '../types';

const MODE_ORDER: TravelMode[] = ['walking', 'bicycle', 'motorcycle', 'driving'];
const MODE_ICONS: Record<TravelMode, React.ComponentType<{ className?: string }>> = {
  walking: Footprints,
  bicycle: Bike,
  motorcycle: Motorbike,
  driving: Car,
};
const LEVEL_LABELS = { slow: 'Slow', moderate: 'Moderate', heavy: 'Heavy', closed: 'Closed' } as const;

// Delay as a share of the free-flow time -> colour of the "+N min" note.
const delayTone = (route: RouteOption) => {
  const traffic = route.traffic;
  if (!traffic || traffic.delay_s < 60) return 'text-ab-success';
  const base = traffic.free_flow_duration_s ?? route.duration_s - traffic.delay_s;
  const ratio = base > 0 ? traffic.delay_s / base : 0;
  return ratio >= 0.5 ? 'text-ab-danger' : ratio >= 0.2 ? 'text-ab-warning' : 'text-ab-muted';
};

const delayText = (route: RouteOption) =>
  route.traffic && route.traffic.delay_s >= 60 ? `+${formatMinutes(route.traffic.delay_s)} traffic` : 'no traffic delay';

const TAG_LABELS: Record<RouteTag, string> = {
  shortest_distance: 'Shortest distance',
  shortest_time: 'Shortest time',
  alternative: 'Alternative',
};

/** Workplace → property accessibility (decision support).
 *
 *  Everything shown comes from the routing provider via the ALTY API: road
 *  distance and travel time per mode, and alternative routes with factual
 *  labels. It informs the choice; it never ranks the property for the user.
 *  Straight-line distance is shown separately and labelled as geographic. */
export const CommuteCard: React.FC<CommuteCardProps> = ({
  property,
  workplace,
  onSetWorkplaceClick,
  routeSelection,
  onRouteSelectionChange,
  onViewRoute,
  commute,
}) => {
  // Use the page's shared state when given; otherwise load it here.
  const own = useCommute(commute ? null : workplace, property);
  const { result, error, isLoading, updatedAt, refresh } = commute ?? own;
  const [localSelection, setLocalSelection] = useState<RouteSelection>({ mode: 'driving', routeId: 'A' });
  const selection = routeSelection ?? localSelection;
  const select = (next: RouteSelection) => (onRouteSelectionChange ?? setLocalSelection)(next);

  if (!workplace) {
    return (
      <div className="rounded-xl border border-dashed border-ab-border-strong bg-ab-card p-4 text-center">
        <Briefcase className="mx-auto mb-1.5 h-6 w-6 text-ab-accent" />
        <p className="text-sm font-semibold text-ab-text">How far is this from work?</p>
        <p className="mx-auto mb-3 mt-1 max-w-xs text-xs text-ab-muted">
          Set your workplace to compare road distance and travel time by walking, bicycle, motorcycle and car.
        </p>
        <button
          type="button"
          onClick={onSetWorkplaceClick}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-ab-accent px-4 py-2 text-sm font-semibold text-ab-ink transition hover:bg-ab-accent-hover"
        >
          <Briefcase className="h-4 w-4" />
          Set Workplace
        </button>
      </div>
    );
  }

  if (property.lat == null || property.lng == null) {
    return (
      <div className="rounded-xl border border-ab-border bg-ab-card p-4 text-xs text-ab-muted">
        This property has no map location yet, so commute routes can't be calculated.
      </div>
    );
  }

  const modeResult = result?.modes[selection.mode];
  const routes = modeResult?.status === 'ok' ? modeResult.routes : [];
  const activeRoute = routes.find((route) => route.id === selection.routeId) ?? routes[0];
  const liveTraffic = activeRoute?.traffic;
  const jams = liveTraffic?.segments.filter((segment) => segment.level !== 'slow') ?? [];

  return (
    <section aria-label="Commute from workplace" className="rounded-xl border border-ab-border bg-ab-card p-4">
      <div className="flex items-start justify-between gap-3 border-b border-ab-border pb-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ab-faint">Commute from workplace</p>
          <p className="mt-1 flex items-center gap-1.5 truncate text-sm font-semibold text-ab-text">
            <Briefcase className="h-3.5 w-3.5 shrink-0 text-ab-accent" />
            <span className="truncate">{workplace.name}</span>
          </p>
        </div>
        <button type="button" onClick={onSetWorkplaceClick} className="shrink-0 text-xs font-semibold text-ab-accent hover:underline">
          Change
        </button>
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 py-4 text-sm text-ab-muted" role="status">
          <LoaderCircle className="h-4 w-4 animate-spin text-ab-accent" />
          Calculating road routes…
        </p>
      )}

      {error && (
        <p className="mt-3 flex items-start gap-2 rounded-lg border border-ab-warning/40 bg-ab-warning/10 p-3 text-xs text-ab-warning" role="alert">
          <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </p>
      )}

      {result && (
        <>
          <ul className="mt-3 space-y-1.5">
            {MODE_ORDER.map((mode) => {
              const item = result.modes[mode];
              const Icon = MODE_ICONS[mode];
              const primary = item.routes[0];
              const isActive = selection.mode === mode;
              const usable = item.status === 'ok' && primary;
              return (
                <li key={mode}>
                  <button
                    type="button"
                    disabled={!usable}
                    aria-pressed={isActive}
                    onClick={() => select({ mode, routeId: primary?.id ?? 'A' })}
                    className={`flex min-h-11 w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition ${
                      isActive && usable
                        ? 'border-ab-accent bg-ab-accent-soft'
                        : 'border-ab-border bg-ab-card-2 hover:bg-ab-hover'
                    } disabled:cursor-default disabled:opacity-70 disabled:hover:bg-ab-card-2`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${isActive && usable ? 'text-ab-accent' : 'text-ab-muted'}`} />
                    <span className="w-24 shrink-0 text-sm font-medium text-ab-text">{item.label}</span>
                    {usable ? (
                      <span className="ml-auto text-right text-sm tabular-nums text-ab-text">
                        {formatKm(primary.distance_m)} <span className="text-ab-faint">·</span>{' '}
                        <strong>{formatMinutes(primary.duration_s)}</strong>
                        {primary.traffic && (
                          <span className={`block text-[10px] font-medium ${delayTone(primary)}`}>{delayText(primary)}</span>
                        )}
                      </span>
                    ) : (
                      <span className="ml-auto text-right text-[11px] leading-snug text-ab-faint">
                        {item.status === 'unsupported' ? 'Not available from the routing provider' : item.message}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>

          {routes.length > 1 && (
            <div className="mt-3">
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-ab-faint">
                Route options · {result.modes[selection.mode].label}
              </p>
              <div className="grid gap-1.5">
                {routes.map((route) => (
                  <button
                    key={route.id}
                    type="button"
                    aria-pressed={selection.routeId === route.id}
                    onClick={() => select({ mode: selection.mode, routeId: route.id })}
                    className={`flex min-h-10 items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-xs transition ${
                      selection.routeId === route.id ? 'border-ab-accent bg-ab-accent-soft' : 'border-ab-border bg-ab-card-2 hover:bg-ab-hover'
                    }`}
                  >
                    <span className="shrink-0 font-bold text-ab-text">Route {route.id}</span>
                    <span className="shrink-0 whitespace-nowrap tabular-nums text-ab-muted">
                      {formatKm(route.distance_m)} · {formatMinutes(route.duration_s)}
                      {route.traffic && route.traffic.delay_s >= 60 && (
                        <span className={`ml-1 ${delayTone(route)}`}>(+{formatMinutes(route.traffic.delay_s)})</span>
                      )}
                    </span>
                    <span className="ml-auto flex min-w-0 flex-wrap justify-end gap-1">
                      {route.tags.map((tag) => (
                        <span key={tag} className="rounded-full border border-ab-border px-1.5 py-0.5 text-[10px] font-medium text-ab-muted">
                          {TAG_LABELS[tag]}
                        </span>
                      ))}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {liveTraffic && activeRoute && (
            <div className="mt-3 rounded-lg border border-ab-border bg-ab-card-2 p-3 text-xs" aria-label="Live traffic on this route">
              <p className="mb-2 flex items-center gap-1.5 font-semibold text-ab-text">
                <TrafficCone className="h-3.5 w-3.5 text-ab-warning" />
                Live traffic · Route {activeRoute.id}
              </p>
              <dl className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-ab-faint">Now</dt>
                  <dd className="text-sm font-bold tabular-nums text-ab-text">{formatMinutes(activeRoute.duration_s)}</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-ab-faint">Usually</dt>
                  <dd className="text-sm font-semibold tabular-nums text-ab-muted">
                    {liveTraffic.typical_duration_s != null ? formatMinutes(liveTraffic.typical_duration_s) : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-wide text-ab-faint">No traffic</dt>
                  <dd className="text-sm font-semibold tabular-nums text-ab-muted">
                    {liveTraffic.free_flow_duration_s != null ? formatMinutes(liveTraffic.free_flow_duration_s) : '—'}
                  </dd>
                </div>
              </dl>
              <p className={`mt-2 ${delayTone(activeRoute)}`}>
                {liveTraffic.delay_s >= 60
                  ? `Traffic adds ${formatMinutes(liveTraffic.delay_s)} right now`
                  : 'No significant traffic delay right now'}
                {jams.length > 0 &&
                  ` · ${jams.length} congested stretch${jams.length > 1 ? 'es' : ''} (${jams
                    .map((segment) => LEVEL_LABELS[segment.level].toLowerCase())
                    .join(', ')})`}
              </p>
            </div>
          )}

          {onViewRoute && routes.length > 0 && (
            <button
              type="button"
              onClick={onViewRoute}
              className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-1.5 rounded-xl border border-ab-border-strong bg-ab-card-2 px-3 py-2 text-sm font-semibold text-ab-text transition hover:bg-ab-hover"
            >
              <Route className="h-4 w-4 text-ab-accent" />
              View route on map
            </button>
          )}

          <div className="mt-3 space-y-1 border-t border-ab-border pt-2.5 text-[11px] leading-snug text-ab-faint">
            <p className="flex items-start gap-1.5">
              <Navigation className="mt-0.5 h-3 w-3 shrink-0" />
              Straight-line (geographic) distance: {formatKm(result.straight_line_m)} — not a travel distance.
            </p>
            <p className="flex items-start gap-1.5">
              <Info className="mt-0.5 h-3 w-3 shrink-0" />
              <span>
                {result.live_traffic
                  ? 'Car and motorcycle times include live traffic; walking and bicycle times do not depend on traffic.'
                  : result.traffic.available
                    ? 'Travel times are typical road times; the Traffic layer shows current congestion.'
                    : 'Travel times are typical road times. Live traffic data is not available.'}
                {result.live_traffic && updatedAt && (
                  <>
                    {' '}Updated {updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ·{' '}
                    <button type="button" onClick={refresh} className="inline-flex items-center gap-0.5 font-semibold text-ab-accent hover:underline">
                      <RefreshCw className="h-3 w-3" /> Refresh
                    </button>
                  </>
                )}
              </span>
            </p>
            {result.attribution && <p className="pl-[18px]">{result.attribution}</p>}
          </div>
        </>
      )}
    </section>
  );
};
