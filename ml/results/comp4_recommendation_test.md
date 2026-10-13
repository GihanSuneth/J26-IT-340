# Component 4 — Recommendation Test

## Test setup
- Model: Random Forest Classifier
- Dataset: Simulated Sri Lankan supermarket purchase history
- Test customer: C0118
- Recommendation count: 5

## Preliminary evaluation
- Random Forest Precision@5: 0.442
- Random Forest Recall@5: 0.559
- Recent-purchase baseline Precision@5: 0.341
- Recent-purchase baseline Recall@5: 0.423

## Functional test
The recommendation script accepted a customer ID, processed the customer's historical purchase records, generated model scores, and returned five ranked product recommendations.

## Limitation
The dataset contains simulated purchase events. These results demonstrate prototype functionality and do not establish real-world performance with actual supermarket customers.