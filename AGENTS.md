# Repository guidance

## Project state

- This is an OCR demo, which extracts information from scanned documents and 
  highlight the differeces as an audit process

## Local data

- Store private, machine-specific, downloaded, or otherwise uncommitted data in
  the repository's `data/` directory.
- `data/` contents are ignored by Git. Do not force-add local data or credentials.
- Commit only `data/.gitkeep` to preserve the empty directory in checkouts.

## Working practices

- Do not add dependencies or generated artifacts unless the task needs them.
- Before running project commands, check the repository for an established
  command or workflow; do not assume one exists.
