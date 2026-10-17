import { Replay, SCENARIOS, STATE_LABELS, observationState, transportState, formatAge, modeLabel } from './model.js';

const byId = id => document.getElementById(id);
const text = (id, value) => { if (byId(id).textContent !== value) byId(id).textContent = value; };
let replay = new Replay('recent', performance.now());
let previousStates = '';
let previousEvents = '';
const distances = { left: '1.4', center: '0.9', right: null };

function render(now) {
  replay.tick(now);
  const states = [];
  let connections = 0;
  for (const source of replay.sources) {
    const { state, age } = observationState(source, now);
    const transport = transportState(source, now);
    const kind = source.kind;
    const label = STATE_LABELS[state];
    states.push(`${source.name}: ${label}`);
    connections += Number(transport === 'connected');
    text(`${kind}-summary`, label);
    byId(`${kind}-summary`).dataset.state = state;
    text(`${kind}-summary-age`, `${formatAge(age)}${age === null ? '' : ' upper bound'}`);
    text(`${kind}-status`, label);
    byId(`${kind}-status`).dataset.state = state;
    text(`${kind}-sequence`, `Capture #${source.seq}`);
    text(`${kind}-age`, formatAge(age));
    text(`${kind}-heartbeat`, source.connected ? `${formatAge(now - source.heartbeatAt)} ago` : 'Disconnected');
    text(`${kind}-transport`, transport === 'connected' ? 'Responding' : transport === 'disconnected' ? 'Disconnected' : 'Unavailable');
    if (kind === 'depth') {
      for (const [sector, distance] of Object.entries(distances)) {
        const eligible = state === 'within-budget' && distance !== null;
        text(`sector-${sector}`, eligible ? `${distance} m` : '—');
        text(`sector-${sector}-note`, eligible ? 'Fixture distance' : distance === null ? 'Unknown coverage' : label);
      }
      text('depth-note', state === 'within-budget'
        ? 'Right-sector coverage is unknown. Distances are synthetic observations, not route guidance.'
        : state === 'expired' ? 'Depth has expired. Heartbeats cannot make an old capture fresh.'
        : state === 'unknown' ? 'Depth or capture age is unknown. No distance is inferred.'
        : 'Source unavailable. Previous distances are removed.');
    } else {
      byId('preview-boxes').setAttribute('visibility', state === 'within-budget' ? 'visible' : 'hidden');
      byId('preview-unavailable').setAttribute('visibility', state === 'within-budget' ? 'hidden' : 'visible');
      text('vision-frame', `fixture-frame-${source.seq}`);
      text('vision-note', state === 'within-budget' ? 'Synthetic object evidence only. No real model or inference worker is connected.'
        : state === 'expired' ? 'Vision has expired. Object boxes are removed; signal state remains unknown.'
        : 'No eligible vision observation. Object boxes are removed; signal state remains unknown.');
    }
  }
  text('mode-label', modeLabel('replay'));
  text('transport-summary', connections === 2 ? 'Responding' : connections ? 'Partial' : 'Unavailable');
  text('transport-detail', `${connections} of 2 responding`);
  const summary = states.join('. ');
  if (summary !== previousStates) {
    text('announcements', summary);
    previousStates = summary;
  }
  const fingerprint = replay.events.map(event => `${event.at}:${event.text}`).join('|');
  if (fingerprint !== previousEvents) {
    const events = replay.events.map(event => {
      const row = document.createElement('li');
      const time = document.createElement('span');
      const body = document.createElement('span');
      time.className = 'event-time';
      time.textContent = `+${((event.at - replay.startedAt) / 1000).toFixed(1)}s`;
      body.textContent = event.text;
      row.append(time, body);
      return row;
    });
    byId('events').replaceChildren(...events);
    previousEvents = fingerprint;
  }
}

byId('scenario').addEventListener('change', event => {
  replay = new Replay(event.target.value, performance.now());
  text('scenario-note', SCENARIOS[replay.scenario].note);
  byId('pause').setAttribute('aria-pressed', 'false');
  text('pause', 'Pause replay Ⅱ');
  render(performance.now());
});

byId('pause').addEventListener('click', () => {
  replay.paused = !replay.paused;
  byId('pause').setAttribute('aria-pressed', String(replay.paused));
  text('pause', replay.paused ? 'Resume replay ▷' : 'Pause replay Ⅱ');
  text('scenario-note', replay.paused ? 'Replay packets paused. Capture ages keep advancing and transport will expire.' : SCENARIOS[replay.scenario].note);
  render(performance.now());
});

render(performance.now());
setInterval(() => render(performance.now()), 100);
// Catch up immediately after tab suspension; frozen rendering never freezes age.
document.addEventListener('visibilitychange', () => render(performance.now()));
