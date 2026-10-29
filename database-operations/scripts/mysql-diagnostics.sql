-- Oracle MySQL 8.4 baseline, not MariaDB. Explicit approved client target.
-- Session timeout applies to eligible SELECTs; no query text or client identity.
SET SESSION max_execution_time = 5000;
SELECT VERSION() AS engine_version, @@global.max_connections AS max_connections,
       @@global.read_only AS read_only, @@global.super_read_only AS super_read_only;
SHOW GLOBAL STATUS WHERE Variable_name IN
 ('Uptime','Threads_connected','Threads_running','Max_used_connections',
  'Connections','Aborted_connects','Connection_errors_max_connections',
  'Questions','Slow_queries','Created_tmp_disk_tables',
  'Innodb_buffer_pool_reads','Innodb_buffer_pool_read_requests');
SELECT THREAD_ID, PROCESSLIST_ID, PROCESSLIST_COMMAND, PROCESSLIST_TIME, PROCESSLIST_STATE
FROM performance_schema.threads
WHERE TYPE = 'FOREGROUND' AND PROCESSLIST_ID IS NOT NULL
ORDER BY PROCESSLIST_TIME DESC LIMIT 50;
SELECT REQUESTING_ENGINE_TRANSACTION_ID, BLOCKING_ENGINE_TRANSACTION_ID
FROM performance_schema.data_lock_waits LIMIT 50;
