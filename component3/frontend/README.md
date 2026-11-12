# Component 3 frontend

Frontend assets are grouped by user-facing responsibility:

- `navigation/` contains the trolley-display navigation JSX components and the
  customer/operator navigation dashboard.
- `recommendation/` contains the recommendation card and standalone
  recommendation dashboard.
- `shared/` contains browser behaviour shared by both dashboard modes.

The Python dashboard server maps these files to stable browser URLs; moving the
assets here does not change the customer-facing routes.
