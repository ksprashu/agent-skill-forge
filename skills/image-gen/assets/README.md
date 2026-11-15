# Assets Directory

Place reusable brand style guides, character turnaround sheets, or prop references here when grounding visual series with `-r` / `--reference` (`char:path.png`, `style:path.png`, `prop:path.png`, `anchor:path.png`) in `<skill-dir>/scripts/image_gen.py`.

Assets larger than 12 MB or reused across multi-frame `--manifest` runs and retries are uploaded once via `gemini-api files upload <path> --wait` and cached as `files/<id>` URIs automatically.
