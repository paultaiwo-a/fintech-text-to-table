-- Monthly volume and switching rate by primary pain point
SELECT strftime('%Y-%m', interaction_date) AS month,
       primary_pain_point,
       COUNT(*) AS interactions,
       ROUND(AVG(switching_intent), 3) AS switching_rate
FROM fct_interaction
WHERE needs_review = 0
GROUP BY 1, 2
ORDER BY 1, 2;
