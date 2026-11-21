-- Top acquisition signals in the latest 90 days of the data
SELECT interaction_id,
       product,
       state,
       primary_pain_point,
       amount_usd_max,
       switching_intent,
       lead_signal_score
FROM fct_interaction
WHERE interaction_date >= (
        SELECT DATE(MAX(interaction_date), '-90 days') FROM fct_interaction
      )
  AND lead_signal_score >= 75
ORDER BY lead_signal_score DESC, amount_usd_max DESC
LIMIT 100;
