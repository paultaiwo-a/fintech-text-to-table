-- Which pain points drive switching? (volume floor = 50; exclude 'none')
SELECT primary_pain_point AS pain_point_code,
       COUNT(*)                          AS interactions,
       ROUND(AVG(switching_intent), 4)   AS switching_rate,
       ROUND(AVG(sentiment_score), 2)    AS avg_sentiment,
       ROUND(AVG(severity_score), 1)     AS avg_severity,
       ROUND(AVG(lead_signal_score), 1)  AS avg_lead_score,
       SUM(CASE WHEN lead_signal_score >= 75 THEN 1 ELSE 0 END) AS hot_leads
FROM fct_interaction
WHERE needs_review = 0
  AND primary_pain_point != 'none'
GROUP BY primary_pain_point
HAVING COUNT(*) >= 50
ORDER BY switching_rate DESC;
