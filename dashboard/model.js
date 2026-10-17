// Local display model for synthetic fixtures. This is not a wire protocol or
// a device freshness/policy implementation. Never compare device clocks here.
export const BUDGETS = Object.freeze({ depth: 500, vision: 1500, transport: 2500 });

export function ageUpperBound(observation, now) {
  if (!observation || !Number.isFinite(now) || !Number.isFinite(observation.receivedAt)
      || !Number.isFinite(observation.ageAtReceipt) || observation.ageAtReceipt < 0
      || now < observation.receivedAt) return null;
  const age = observation.ageAtReceipt + (now - observation.receivedAt);
  return Number.isFinite(age) ? age : null;
}

export function transportState(source, now) {
  if (!source?.connected) return 'disconnected';
  if (!Number.isFinite(source.heartbeatAt) || !Number.isFinite(now)
      || now < source.heartbeatAt || now - source.heartbeatAt > BUDGETS.transport) return 'unavailable';
  return 'connected';
}

export function observationState(source, now) {
  const age = ageUpperBound(source?.observation, now);
  if (transportState(source, now) !== 'connected') return { state: 'unavailable', age };
  if (source.kind !== 'depth' && source.kind !== 'vision') return { state: 'unknown', age };
  if (age === null) return { state: 'unknown', age: null };
  if (age > BUDGETS[source.kind]) return { state: 'expired', age };
  if (!source.observation.known) return { state: 'unknown', age };
  return { state: 'within-budget', age };
}

export function formatAge(value) {
  if (!Number.isFinite(value) || value < 0) return 'Unknown';
  if (value >= 1000) return `${(value / 1000).toFixed(1)} s`;
  return `${Math.ceil(value)} ms`;
}

export function modeLabel(mode) {
  return mode === 'live' ? 'Live' : mode === 'replay' ? 'Replay' : 'Unknown mode';
}

export const STATE_LABELS = Object.freeze({
  'within-budget': 'Within age budget', expired: 'Expired', unknown: 'Unknown', unavailable: 'Unavailable',
});

export const SCENARIOS = Object.freeze({
  recent: { label: 'Recent observations', note: 'Synthetic captures and heartbeats arrive independently.' },
  'unknown-depth': { label: 'Unknown depth', note: 'Transport works; missing depth remains unknown.' },
  delayed: { label: 'Delayed vision', note: 'The vision capture-age bound exceeds 1,500 ms.' },
  heartbeat: { label: 'Heartbeats only', note: 'Heartbeats continue. Without new captures, observations expire.' },
  uncertain: { label: 'Clock uncertainty', note: 'An unbounded capture age stays unknown; receipt time cannot replace it.' },
  'phone-disconnected': { label: 'Phone disconnected', note: 'Phone depth is unavailable; independent synthetic Pi vision continues.' },
  'pi-disconnected': { label: 'Pi disconnected', note: 'Pi vision is unavailable; independent synthetic phone depth continues.' },
  disconnected: { label: 'Sources disconnected', note: 'Lost transport makes source observations unavailable immediately.' },
});

export class Replay {
  constructor(scenario = 'recent', now = 0) {
    if (!Object.hasOwn(SCENARIOS, scenario)) throw new Error('Unknown replay scenario');
    this.scenario = scenario;
    this.startedAt = now;
    this.paused = false;
    this.sources = [
      { id: 'fixture-phone', name: 'Phone depth', kind: 'depth', seq: 0, connected: !['disconnected', 'phone-disconnected'].includes(scenario), heartbeatAt: now, observation: null },
      { id: 'fixture-pi', name: 'Pi vision', kind: 'vision', seq: 0, connected: !['disconnected', 'pi-disconnected'].includes(scenario), heartbeatAt: now, observation: null },
    ];
    this.events = [];
    for (const source of this.sources) if (source.connected) this.capture(source, now);
    this.lastCapture = { depth: now, vision: now };
    this.lastHeartbeat = now;
  }

  event(text, now) {
    this.events.unshift({ text, at: now });
    this.events.length = Math.min(this.events.length, 8);
  }

  capture(source, now) {
    source.seq += 1;
    source.observation = {
      receivedAt: now,
      ageAtReceipt: this.scenario === 'uncertain' ? null : source.kind === 'vision' && this.scenario === 'delayed' ? 2200 : source.kind === 'depth' ? 120 : 180,
      known: !(source.kind === 'depth' && this.scenario === 'unknown-depth'),
    };
    this.event(`${source.name}: synthetic capture #${source.seq}`, now);
  }

  tick(now) {
    if (this.paused || this.scenario === 'disconnected') return;
    if (now - this.lastHeartbeat >= 500) {
      for (const source of this.sources) if (source.connected) source.heartbeatAt = now;
      this.lastHeartbeat = now;
    }
    if (this.scenario === 'heartbeat') return;
    for (const source of this.sources) {
      if (source.connected && now - this.lastCapture[source.kind] >= (source.kind === 'depth' ? 200 : 1000)) {
        this.capture(source, now);
        this.lastCapture[source.kind] = now;
      }
    }
  }
}
