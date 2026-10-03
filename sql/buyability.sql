-- Registered inputs: eligible (one row per county), scenarios (annual decimal rates).
-- This is principal and interest ONLY, not a complete housing-cost ratio.
CREATE OR REPLACE TABLE buyability AS
WITH payments AS (
    SELECT e.*, s.scenario, s.annual_rate,
           price_2024 * 0.8 AS principal,
           CASE WHEN s.annual_rate = 0 THEN price_2024 * 0.8 / 360
                ELSE price_2024 * 0.8 * (s.annual_rate / 12)
                  / (1 - pow(1 + s.annual_rate / 12, -360)) END AS monthly_pi
    FROM eligible e CROSS JOIN scenarios s
)
SELECT *, monthly_pi * 12 / income AS pti_all,
          monthly_pi * 12 / renter_income AS pti_renter,
          price_2024 * 0.2 / income AS down_payment_to_annual_income,
          price_2024 * 0.2 / renter_income AS down_payment_to_renter_income,
          monthly_pi * 12 / (income + income_moe) AS pti_income_moe_low,
          CASE WHEN income > income_moe THEN monthly_pi * 12 / (income - income_moe) END AS pti_income_moe_high
FROM payments;
