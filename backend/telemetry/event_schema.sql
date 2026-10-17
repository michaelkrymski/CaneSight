CREATE TABLE IF NOT EXISTS canesight_event_rows (
    event_id uuid PRIMARY KEY,
    stream_id uuid NOT NULL,
    observed_minute timestamptz NOT NULL,
    mode text NOT NULL CHECK (mode IN ('live', 'replay')),
    role text NOT NULL CHECK (role IN ('phone', 'pi')),
    event_kind text NOT NULL CHECK (event_kind IN
        ('frame_accepted', 'depth_admitted', 'heartbeat_admitted', 'vision_offered')),
    expires_at timestamptz NOT NULL,
    CHECK (observed_minute = date_trunc('minute', observed_minute)),
    CHECK (expires_at = observed_minute + INTERVAL '24 hours')
);
CREATE INDEX IF NOT EXISTS canesight_events_expiry ON canesight_event_rows (expires_at);
CREATE INDEX IF NOT EXISTS canesight_events_stream ON canesight_event_rows (stream_id);
CREATE OR REPLACE VIEW canesight_events AS
    SELECT event_id, stream_id, observed_minute, mode, role, event_kind,
           NULL::double precision AS capture_age_upper_ms, expires_at
    FROM canesight_event_rows WHERE expires_at > clock_timestamp();
