-- The quality gate: is the learning loop alive and producing good models?
--
--   make quality-gate
--   (Windows, no make)  docker compose exec -T postgres psql -U recoil -d recoil -v ON_ERROR_STOP=1 -f - < infra/postgres/quality_gate.sql
--
-- Passes only if ALL of these hold, otherwise psql exits non-zero (so a script or CI job fails):
--   1. at least one model has ever been promoted
--   2. the most recent promoted model cleared the 0.65 AUC gate
--   3. that promotion was recent: the loop is still turning, not frozen
--      (this is the check that would have caught the phase-9 freeze)

DO $gate$
DECLARE
    latest record;
    runs_last_hour int;
BEGIN
    SELECT model_version, auc, finished_at
      INTO latest
      FROM training_runs
     WHERE promoted
     ORDER BY run_id DESC
     LIMIT 1;

    IF latest IS NULL THEN
        RAISE EXCEPTION 'QUALITY GATE FAILED: no model has ever been promoted';
    END IF;

    IF latest.auc < 0.65 THEN
        RAISE EXCEPTION 'QUALITY GATE FAILED: % has AUC % (< 0.65)', latest.model_version, round(latest.auc::numeric, 4);
    END IF;

    IF latest.finished_at < now() - interval '10 minutes' THEN
        RAISE EXCEPTION 'QUALITY GATE FAILED: last promotion (%) was more than 10 minutes ago; the loop looks frozen',
            latest.finished_at;
    END IF;

    SELECT count(*) INTO runs_last_hour
      FROM training_runs
     WHERE started_at > now() - interval '1 hour';

    RAISE NOTICE 'QUALITY GATE PASSED: % AUC=% promoted at %, % training runs in the last hour',
        latest.model_version, round(latest.auc::numeric, 4), latest.finished_at, runs_last_hour;
END
$gate$;
