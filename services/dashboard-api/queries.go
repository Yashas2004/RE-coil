package main

// All the SQL lives here, so you can read exactly what the dashboard measures.

// Every interaction is labelled with the model_version that served it.
// We group those labels into three "variants":
//
//	control -> the A/B holdout group (trending feed, no model)
//	random  -> no feed available, bots picked at random (the cold-start baseline)
//	model   -> any trained model version
const variantExpr = `
	CASE
		WHEN model_version = 'control' THEN 'control'
		WHEN model_version IS NULL OR model_version IN ('random', 'trending', 'unknown') THEN 'random'
		ELSE 'model'
	END`

// Watch rate per minute per variant: the chart that shows the loop learning.
const watchRateSQL = `
	SELECT date_trunc('minute', created_at) AS minute,
	       ` + variantExpr + ` AS variant,
	       count(*) AS shown,
	       sum(CASE WHEN watched THEN 1 ELSE 0 END) AS watched
	FROM interactions
	WHERE created_at > now() - make_interval(mins => $1)
	GROUP BY 1, 2
	ORDER BY 1, 2`

// The A/B scoreboard: same time window, two groups, compare.
const abSQL = `
	SELECT ` + variantExpr + ` AS variant,
	       count(*) AS shown,
	       sum(CASE WHEN watched THEN 1 ELSE 0 END) AS watched,
	       count(DISTINCT user_id) AS users
	FROM interactions
	WHERE created_at > now() - make_interval(mins => $1)
	GROUP BY 1
	ORDER BY 1`

const trainingRunsSQL = `
	SELECT model_version, num_samples, coalesce(auc, 0), promoted,
	       started_at, coalesce(finished_at, started_at)
	FROM training_runs
	ORDER BY run_id DESC
	LIMIT $1`

const countsSQL = `
	SELECT (SELECT count(*) FROM videos),
	       (SELECT count(*) FROM users),
	       (SELECT count(*) FROM interactions),
	       (SELECT count(*) FROM interactions WHERE created_at > now() - interval '1 minute')`

const categoriesSQL = `SELECT video_id, category, title FROM videos WHERE video_id = ANY($1)`
