-- Which pain points drive switching? (volume floor = 500)
SELECT p.pain_point_code,
       COUNT(*)                         AS interactions,
       ROUND(AVG(f.switching_intent), 3) AS switching_rate,
       ROUND(AVG(f.sentiment_score), 2)  AS avg_sentiment,
       ROUND(AVG(f.severity_score), 1)   AS avg_severity
FROM fct_interaction_pain_point p
JOIN fct_interaction f USING (interaction_id)
WHERE f.needs_review = 0
GROUP BY p.pain_point_code
HAVING COUNT(*) >= 500
ORDER BY switching_rate DESC;
