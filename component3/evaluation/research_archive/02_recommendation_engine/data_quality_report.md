# Data quality report

All 10,000 rows parsed; required-field missingness and exact duplicate-row count are
zero. There are 1,991 internally consistent order groups. Quantities are positive
integers (1–3), and prices are positive (10.09–499.96). No branch, cancellation,
return, refund, currency, or line-status field exists, so their absence cannot be
inferred from positive quantities.

The central defect is identifier validity: all 900 `product_id` values occur with
multiple product names, and all 68 names occur under multiple IDs. Source product IDs
therefore cannot be treated as SKUs. There are 296 order/name pairs with repeated lines,
representing 299 extra lines; these are aggregated by normalized name and summed
quantity. Product names have stable categories in this file.

The data is suitable for basket prevalence, association, and item-item experiments at
the 68-name vocabulary level. It is not currently suitable for SKU-level learning,
user-personalized claims, or verified sequential recommendations. Machine-readable
details are in `data_quality.json`.
