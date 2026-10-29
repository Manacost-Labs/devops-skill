-- MariaDB 11.4 baseline, not Oracle MySQL. Explicit approved client target.
-- Session-scoped bound; do not expose INFO, USER, HOST or raw InnoDB status.
SET SESSION max_statement_time = 5;
SELECT VERSION() AS engine_version, @@global.max_connections AS max_connections,
       @@global.read_only AS read_only;
SHOW GLOBAL STATUS WHERE Variable_name IN
 ('Uptime','Threads_connected','Threads_running','Max_used_connections',
  'Connections','Aborted_connects','Questions','Slow_queries',
  'Created_tmp_disk_tables','Innodb_buffer_pool_reads','Innodb_buffer_pool_read_requests');
SELECT ID, COMMAND, TIME, STATE FROM information_schema.PROCESSLIST
ORDER BY TIME DESC LIMIT 50;
SELECT requesting_trx_id, blocking_trx_id
FROM information_schema.INNODB_LOCK_WAITS LIMIT 50;
