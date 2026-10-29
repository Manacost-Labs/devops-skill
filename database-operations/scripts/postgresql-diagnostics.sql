-- PostgreSQL 18 baseline; approved target/least-privilege client only.
-- No query text, client identity or user data. Close promptly; no automatic polling.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '1s';
SELECT current_setting('server_version_num') AS server_version_num,
       pg_is_in_recovery() AS in_recovery,
       pg_postmaster_start_time() AS started_at,
       current_setting('max_connections') AS max_connections,
       current_setting('superuser_reserved_connections') AS superuser_reserved;
SELECT state, wait_event_type, count(*) AS sessions
FROM pg_stat_activity GROUP BY state, wait_event_type
ORDER BY sessions DESC LIMIT 30;
SELECT pid, state, wait_event_type, wait_event,
       clock_timestamp() - xact_start AS transaction_age,
       pg_blocking_pids(pid) AS blocking_pids
FROM pg_stat_activity
WHERE datname = current_database() AND pid <> pg_backend_pid()
ORDER BY xact_start NULLS LAST LIMIT 50;
SELECT stats_reset, xact_commit, xact_rollback, blks_read, blks_hit,
       temp_files, temp_bytes, deadlocks
FROM pg_stat_database WHERE datname = current_database();
ROLLBACK;
