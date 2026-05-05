# Art2Vec Website V2

Final first-iteration website for the capstone presentation and public painting exploration.

## Setup

```powershell
npm.cmd install
npm.cmd run data
npm.cmd run dev
```

Use `npm.cmd` on this Windows machine because PowerShell blocks `npm.ps1`.

## Data

`scripts/build_site_data.py` reads the project-level Phase 1 and Phase 2 outputs, computes static Louvain communities for motif networks, and writes:

```text
public/data/artData.json
```

No database is required for this iteration.
