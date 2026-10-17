import { Replay, LiveView, SCENARIOS, STATE_LABELS, observationState, transportState, formatAge, modeLabel } from './model.js';

const byId = id => document.getElementById(id);
const text = (id, value) => { if (byId(id).textContent !== value) byId(id).textContent = value; };
const live = document.body.dataset.feed === 'live';
let replay = live ? new LiveView(performance.now()) : new Replay('recent', performance.now());
let previousStates = '';
let previousEvents = '';
const distances = { left: '1.4', center: '0.9', right: null };

function render(now) {
  if (!live) replay.tick(now);
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
    text(`${kind}-sequence`, live ? source.observation ? `Backend sequence #${source.seq}` : 'No capture metadata' : `Capture #${source.seq}`);
    text(`${kind}-age`, formatAge(age));
    text(`${kind}-heartbeat`, source.connected && Number.isFinite(source.heartbeatAt) ? `${formatAge(now - source.heartbeatAt)} ago` : source.connected ? 'Unknown' : 'Disconnected');
    text(`${kind}-transport`, transport === 'connected' ? live ? 'Backend activity' : 'Responding' : transport === 'disconnected' ? 'Disconnected' : 'Unavailable');
    if (kind === 'depth') {
      for (const [sector, distance] of Object.entries(distances)) {
        const eligible = state === 'within-budget' && distance !== null;
        text(`sector-${sector}`, eligible ? `${distance} m` : '—');
        text(`sector-${sector}-note`, eligible ? 'Fixture distance' : live ? 'Unknown capture age' : distance === null ? 'Unknown coverage' : label);
      }
      text('depth-note', state === 'within-budget'
        ? 'Right-sector coverage is unknown. Distances are synthetic observations, not route guidance.'
        : state === 'expired' ? 'Depth has expired. Heartbeats cannot make an old capture fresh.'
        : state === 'unknown' ? 'Depth or capture age is unknown. No distance is inferred.'
        : 'Source unavailable. Previous distances are removed.');
    } else {
      byId('preview-boxes').setAttribute('visibility', state === 'within-budget' ? 'visible' : 'hidden');
      byId('preview-unavailable').setAttribute('visibility', state === 'within-budget' ? 'hidden' : 'visible');
      text('vision-frame', live ? source.frameId : `fixture-frame-${source.seq}`);
      text('vision-note', state === 'within-budget' ? 'Synthetic object evidence only. No real model or inference worker is connected.'
        : state === 'expired' ? 'Vision has expired. Object boxes are removed; signal state remains unknown.'
        : 'No eligible vision observation. Object boxes are removed; signal state remains unknown.');
    }
  }
  text('mode-label', modeLabel(live ? replay.mode : 'replay'));
  if (live) {
    document.querySelector('.session-chip > span:last-child').textContent = replay.sessionId;
    for (const source of replay.sources) {
      document.querySelector(`.${source.kind === 'depth' ? 'depth' : 'vision'}-panel code`).textContent = source.id;
    }
    document.querySelector('.vision-details dl div:nth-child(2) dd').textContent = replay.sources[1].modelVersion;
    text('vision-note', 'Backend metadata only. Capture age is unknown; boxes and distances stay unavailable. Native Pi receipt is not confirmed by this view.');
    text('depth-note', 'No verified phone-to-backend clock mapping. Depth and capture age remain unknown.');
  }
  text('transport-summary', connections === 2 ? live ? 'Backend activity' : 'Responding' : connections ? 'Partial' : 'Unavailable');
  text('transport-detail', `${connections} of 2 ${live ? 'active at backend' : 'responding'}`);
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
      time.textContent = live ? 'Snapshot' : `+${((event.at - replay.startedAt) / 1000).toFixed(1)}s`;
      body.textContent = event.text;
      row.append(time, body);
      return row;
    });
    byId('events').replaceChildren(...events);
    previousEvents = fingerprint;
  }
}

byId('scenario').addEventListener('change', event => {
  if (live) return;
  replay = new Replay(event.target.value, performance.now());
  text('scenario-note', SCENARIOS[replay.scenario].note);
  byId('pause').setAttribute('aria-pressed', 'false');
  text('pause', 'Pause replay Ⅱ');
  render(performance.now());
});

byId('pause').addEventListener('click', () => {
  if (live) return;
  replay.paused = !replay.paused;
  byId('pause').setAttribute('aria-pressed', String(replay.paused));
  text('pause', replay.paused ? 'Resume replay ▷' : 'Pause replay Ⅱ');
  text('scenario-note', replay.paused ? 'Replay packets paused. Capture ages keep advancing and transport will expire.' : SCENARIOS[replay.scenario].note);
  render(performance.now());
});

if (live) {
  document.querySelector('.replay-controls').hidden = true;
  byId('viewer-access').hidden = false;
  document.querySelector('.fixture-pill').textContent = 'Authenticated session metadata';
  document.querySelector('.sidebar-note .tiny-label').textContent = 'READ-ONLY VIEWER';
  document.querySelector('.sidebar-footer div span').textContent = 'CS-041 · Session metadata';
  document.querySelector('.session-chip > span:last-child').textContent = 'No viewer session';
  document.querySelector('.summary-card:last-child .summary-hint').textContent = 'Socket / backend activity';
  for (const row of document.querySelectorAll('.timing-source dl div:last-child dt')) row.textContent = 'Last backend activity';
  document.querySelector('.activity-panel h2').textContent = 'Backend activity';
  document.querySelector('.activity-panel .outline-tag').textContent = 'Read only';
  document.querySelector('.activity-footer').textContent = 'Latest 8 events · no capture-age inference';
  byId('events').setAttribute('aria-label', 'Recent backend metadata events');
  document.querySelector('.page-footer').textContent = 'Read-only session metadata · capture ages unknown · no movement control';
  document.querySelector('.camera-preview > span').textContent = 'Metadata only · no camera image';
  document.querySelector('#preview-title').textContent = 'No camera image or eligible object boxes in metadata view';
  document.querySelector('.vision-details dl div:last-child dt').textContent = 'Frame / result';
  let polling = false;
  let timer = null;
  let generation = 0;
  let loginBusy = false;
  async function poll(epoch = generation) {
    if (!polling || epoch !== generation) return;
    const started = performance.now();
    try {
      const response = await fetch('/dashboard/api/snapshot', { cache: 'no-store', signal: AbortSignal.timeout(3000) });
      if (!response.ok) throw new Error('Viewer unavailable');
      const snapshot = await response.json();
      if (!polling || epoch !== generation) return;
      replay.apply(snapshot, performance.now(), performance.now() - started);
      text('viewer-note', 'Connected to read-only metadata. Capture ages remain unknown; backend activity does not establish device readiness.');
    } catch {
      if (epoch !== generation) return;
      replay.disconnect();
      text('viewer-note', 'Viewer unavailable or expired. Previous observations removed. Reconnect with a valid viewer credential.');
      polling = false;
    }
    render(performance.now());
    if (polling && epoch === generation) timer = setTimeout(() => poll(epoch), 1000);
  }
  byId('viewer-login').addEventListener('submit', async event => {
    event.preventDefault();
    if (loginBusy) return;
    loginBusy = true;
    byId('viewer-login').querySelector('button').disabled = true;
    byId('viewer-logout').disabled = true;
    clearTimeout(timer); polling = false; replay.disconnect();
    const epoch = ++generation;
    const body = JSON.stringify({ viewer_token: byId('viewer-token').value });
    byId('viewer-token').value = '';
    try {
      const response = await fetch('/dashboard/api/login', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body, signal: AbortSignal.timeout(3000) });
      if (!response.ok) throw new Error('Denied');
      if (epoch !== generation) return;
      polling = true; await poll(epoch);
    } catch { if (epoch === generation) text('viewer-note', 'Viewer login denied. Use a separate unexpired viewer credential.'); }
    finally {
      loginBusy = false;
      byId('viewer-login').querySelector('button').disabled = false;
      byId('viewer-logout').disabled = false;
    }
    render(performance.now());
  });
  byId('viewer-logout').addEventListener('click', async () => {
    if (loginBusy) return;
    generation++; polling = false; clearTimeout(timer); replay.disconnect();
    try { await fetch('/dashboard/api/logout', { method: 'POST', signal: AbortSignal.timeout(3000) }); } catch { /* Local state is already unavailable. */ }
    text('viewer-note', 'Viewer disconnected. No current observation is shown.');
    render(performance.now());
  });
}

render(performance.now());
setInterval(() => render(performance.now()), 100);
// Catch up immediately after tab suspension; frozen rendering never freezes age.
document.addEventListener('visibilitychange', () => render(performance.now()));
