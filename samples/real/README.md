# Real SDS documents (not committed)

Real supplier PDFs are kept **out of Git**. Only this file and
`manifest.example.json` are tracked; everything else in this folder is ignored.

A genuine revision pair must be:

- two genuine revisions of the **same product from the same supplier**,
  unmodified
- in the same language/jurisdiction where possible
- recorded with actual product/supplier identities and a **fictional internal
  material code**, clearly labeled as fictional

Do not edit a real SDS to manufacture a revision, and do not present unrelated
products as a revision pair.

## Provenance

For each file, copy `manifest.example.json` to `manifest.json` (also ignored,
because it describes local files) and record:

- source URL (supplier page or archive capture URL)
- retrieval date
- SHA-256 of the downloaded file
- who retrieved it

An archive such as web.archive.org may or may not hold a suitable older copy.
Supplier pages may block automated access. Neither source is guaranteed.

## Loading a pair (explicit commands, nothing automatic)

1. Add the material:

   ```bash
   .venv/bin/python -m sdstracker add-material --code REAL-DEMO-001 --name "<product>" --supplier "<supplier>" --product-id "<id>"
   ```

2. Record the older revision:

   ```bash
   .venv/bin/python -m sdstracker receive samples/real/<old>.pdf --actor "<name>" --source-url "<url>" --retrieved-on <date>
   ```

3. In the app, confirm the material and designate the older document as the
   baseline.
4. Upload or `receive` the newer revision, confirm its material, and review the
   comparison.
5. Record the results in `docs/results-and-limitations.md`, kept separate from
   the synthetic test results.
