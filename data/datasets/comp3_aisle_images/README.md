<!-- Purpose: document the Component 3 aisle-image dataset area. -->

# Component 3 aisle images

This is a small, manually curated sourcing pilot for the aisle/section image
classifier. It is **not a training-ready dataset**.

## Source and license

The six image files were downloaded from Wikimedia Commons on 2026-10-13.
`ATTRIBUTION.csv` records each Commons file page, creator, and the license
reported on that page. The pilot contains CC0, CC BY 2.0, and CC BY 4.0 items.
Retain attribution and license details when redistributing CC BY images.
Commons notes that image-page licensing metadata is supplied by contributors
and is not a warranty; review each source page and consider other rights before
research publication or deployment.

## Labels and current counts

The initial taxonomy is `produce`, `bakery`, `dairy`, `meat`, `frozen`, and
`general_aisles`, as selected for this project. There is currently one image
per label. The files are organized in matching class subdirectories.

## Splits and limitations

All manifest rows have `split=unassigned`. With only one image per class there
is no valid train/validation/test split and the data must not be used to claim
model performance. The meat image is an archival 1955 black-and-white scene,
which is a substantial domain mismatch for a modern trolley camera. The
produce, dairy, and general-aisle images are from the same Rimi store and
photographer; keep related scenes grouped when a future dataset is split to
avoid leakage.

Expand the dataset with multiple distinct, representative scenes for every
class, review labels, and assign grouped train/validation/test splits before
training. Do not commit the downloaded image files; dataset content remains
ignored by Git.
