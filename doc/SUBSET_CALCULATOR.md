# Subsetting Algorithm

The `restic-subset-calculator` tool strictly follows restic's `n/t` subsetting logic:
- Extracts the first byte of the pack ID (first two hex characters).
- Subset `n` (1-based) is assigned if `first_byte % t == n - 1`.
