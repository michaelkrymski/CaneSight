import test from 'node:test';
import assert from 'node:assert/strict';
import { Replay, ageUpperBound, observationState, transportState, formatAge, modeLabel } from '../../dashboard/model.js';

test('capture-age budgets are independent and expire strictly after their boundaries', () => {
  const replay = new Replay('recent', 0);
  const [depth, vision] = replay.sources;
  assert.equal(observationState(depth, 380).state, 'within-budget');
  assert.equal(observationState(depth, 381).state, 'expired');
  assert.equal(observationState(vision, 1320).state, 'within-budget');
  assert.equal(observationState(vision, 1321).state, 'expired');
});

test('heartbeats keep transport responsive without renewing capture age', () => {
  const replay = new Replay('heartbeat', 0);
  for (let now = 0; now <= 6000; now += 100) replay.tick(now);
  for (const source of replay.sources) {
    assert.equal(source.seq, 1);
    assert.equal(transportState(source, 6000), 'connected');
    assert.equal(observationState(source, 6000).state, 'expired');
    assert.ok(observationState(source, 6000).age >= 6000);
  }
});

test('pause stops packets while old captures and transport continue aging', () => {
  const replay = new Replay('recent', 0);
  replay.paused = true;
  replay.tick(1600);
  assert.ok(replay.sources.every(source => observationState(source, 1600).state === 'expired'));
  replay.tick(2600);
  assert.ok(replay.sources.every(source => observationState(source, 2600).state === 'unavailable'));
  assert.ok(replay.sources.every(source => source.seq === 1));
  replay.paused = false;
  replay.tick(2700);
  assert.ok(replay.sources.every(source => observationState(source, 2700).state === 'within-budget'));
  assert.ok(replay.sources.every(source => source.seq === 2));
});

test('missing, negative, nonfinite and future-clock bounds remain unknown', () => {
  for (const ageAtReceipt of [null, undefined, -1, NaN, Infinity]) {
    assert.equal(ageUpperBound({ receivedAt: 0, ageAtReceipt }, 1), null);
  }
  assert.equal(ageUpperBound({ receivedAt: 2, ageAtReceipt: 10 }, 1), null);
  assert.equal(ageUpperBound({ receivedAt: 0, ageAtReceipt: 10 }, NaN), null);
  const replay = new Replay('uncertain', 0);
  replay.tick(1000);
  assert.ok(replay.sources.every(source => observationState(source, 1000).state === 'unknown'));
});

test('unknown depth is separate from responding transport and recent capture', () => {
  const [depth, vision] = new Replay('unknown-depth', 0).sources;
  assert.equal(observationState(depth, 50).state, 'unknown');
  assert.equal(transportState(depth, 50), 'connected');
  assert.equal(observationState(vision, 50).state, 'within-budget');
});

test('delayed vision does not invalidate an independent current depth fixture', () => {
  const [depth, vision] = new Replay('delayed', 0).sources;
  assert.equal(observationState(depth, 0).state, 'within-budget');
  assert.equal(observationState(vision, 0).state, 'expired');
  assert.equal(observationState(vision, 0).age, 2200);
});

test('disconnect removes observation availability even at a recent capture age', () => {
  const replay = new Replay('recent', 0);
  for (const source of replay.sources) source.connected = false;
  replay.tick(100);
  assert.ok(replay.sources.every(source => observationState(source, 100).state === 'unavailable'));
  assert.ok(replay.sources.every(source => source.seq === 1));
});

test('heartbeat timeout, invalid local clock and unknown source kind fail closed', () => {
  const source = new Replay('recent', 0).sources[0];
  assert.equal(transportState(source, 2500), 'connected');
  assert.equal(transportState(source, 2501), 'unavailable');
  assert.equal(transportState(source, -1), 'unavailable');
  source.kind = 'unexpected';
  assert.equal(observationState(source, 0).state, 'unknown');
});

test('replay retains only eight events and separate capture cadence', () => {
  const replay = new Replay('recent', 0);
  for (let now = 0; now <= 100000; now += 100) replay.tick(now);
  assert.equal(replay.events.length, 8);
  assert.equal(replay.sources[0].seq, 501);
  assert.equal(replay.sources[1].seq, 101);
  assert.throws(() => new Replay('toString'), /Unknown replay scenario/);
});

test('mode and age formatting preserve unknown values', () => {
  assert.equal(modeLabel('live'), 'Live');
  assert.equal(modeLabel('replay'), 'Replay');
  assert.equal(modeLabel(null), 'Unknown mode');
  assert.equal(formatAge(null), 'Unknown');
  assert.equal(formatAge(NaN), 'Unknown');
  assert.equal(formatAge(0), '0 ms');
  assert.equal(formatAge(1100), '1.1 s');
});

test('one disconnected source cannot renew or invalidate its independent peer', () => {
  for (const scenario of ['phone-disconnected', 'pi-disconnected']) {
    const replay = new Replay(scenario, 0);
    const lost = replay.sources.find(source => !source.connected);
    const peer = replay.sources.find(source => source.connected);
    for (let now = 0; now <= 6000; now += 100) replay.tick(now);
    assert.equal(lost.seq, 0);
    assert.equal(lost.observation, null);
    assert.equal(lost.heartbeatAt, 0);
    assert.equal(observationState(lost, 6000).state, 'unavailable');
    assert.equal(transportState(peer, 6000), 'connected');
    assert.equal(observationState(peer, 6000).state, 'within-budget');
    replay.paused = true;
    replay.tick(9000);
    assert.ok(replay.sources.every(source => observationState(source, 9000).state === 'unavailable'));
    replay.paused = false;
    replay.tick(9100);
    assert.equal(observationState(lost, 9100).state, 'unavailable');
    assert.equal(observationState(peer, 9100).state, 'within-budget');
  }
});

test('overflowing age arithmetic stays unknown instead of yielding an infinite bound', () => {
  assert.equal(ageUpperBound({receivedAt: 0, ageAtReceipt: Number.MAX_VALUE}, Number.MAX_VALUE), null);
});
