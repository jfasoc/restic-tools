# Design Document: Restic Subset Calculator

## Goal
Create a tool that calculates the number of packs and the total data size that would be downloaded for each subset `n` when running `restic check --read-data-subset n/t`. This helps users plan their check strategy and understand the distribution of data across subsets.

## Restic Commands
The tool will execute the following commands to gather repository metadata:
1.  `restic list index --json`: To get a list of all index file IDs.
2.  `restic cat index <ID>`: For each index ID, to retrieve its JSON content which contains the mapping of packs to blobs.

## Calculation Logic

### 1. Gathering Pack Information
- The tool will first get the list of index IDs.
- For each index, it will parse the JSON.
- An index contains a list of `packs`. Each pack has an `id` and a list of `blobs`.
- For each pack discovered:
    - The tool will calculate its estimated size: `max(offset + length)` across all its blobs.
    - To avoid double-counting packs that appear in multiple index files, the tool will keep track of seen `pack_id`s.

### 2. The Subsetting Algorithm
The tool will replicate restic's internal subsetting logic:
- A pack belongs to subset `n` (where `1 <= n <= t`) if:
  `int(pack_id[0:2], 16) % t == n - 1`

### 3. Incremental Processing and Output
- The tool will process index files one by one.
- After each index file is processed, it will:
    - Update the cumulative pack counts and sizes for all subsets.
    - Print a header: `Index [current]/[total]`.
    - Print an aligned table showing the current results for each subset `1` to `t`.
- Columns: `Subset (n/t)`, `Packs`, `Size (MB)`.
- Size is in decimal Megabytes (1,000,000 bytes).

## Parameters
- `t` (Required CLI parameter): The total number of subsets to calculate for.
- `--debug`: When enabled, the tool will print the exact restic commands it executes.

## Constraints and Error Handling
- **t Limit**: `t` must be between 1 and 256. If `t > 256`, it is an error.
- **Environment**: Uses existing `RESTIC_REPOSITORY`, `RESTIC_PASSWORD_FILE`, etc.
- **Dependencies**: Pure Python 3 standard library.
