# Running SDS Revision Tracker locally on Zorin OS

> Independent portfolio demonstration. Supports document review; does not make
> safety or regulatory determinations.

Zorin OS is based on Ubuntu, so these steps use Ubuntu packages and a bash
terminal. Open one from Zorin menu → System Tools → Terminal.

**Run every command below on your own computer.** A `localhost` address works
only in a browser on the computer running the app.

## What was tested where

- **Tested in the Claude cloud environment** (Linux, Python 3.13, Streamlit
  1.39.0), marked **[tested in cloud]** below:
  - `./scripts/bootstrap.sh` on a fresh clone
  - `init-db`, `demo-data`, `add-material` and `receive`
  - `streamlit run app.py`, both with and without `SDSTRACKER_DATA_DIR`
  - the `sha256sum -c` check against the stored real PDF
- **Not tested on Zorin OS**, marked **[not tested on Zorin]**: every step on
  your own computer, in particular:
  - the `apt` package installation
  - cloning from GitHub with your credentials
  - downloading the real SDS with plain `curl` (the cloud download used curl
    with a browser-style User-Agent)
  - running on Python 3.10

## 1. Check the Python version

[not tested on Zorin]

```bash
python3 --version
```

You need Python **3.10 or newer**. Zorin OS 17 normally ships 3.10; Zorin OS 16
normally ships 3.8, which is too old for this project. Only Python 3.13 has
actually been tested.

## 2. Install the required system packages

[not tested on Zorin] These ask for your password.

```bash
sudo apt update
```

```bash
sudo apt install -y git python3-venv curl
```

## 3. Clone the repository and select the branch

[not tested on Zorin] If the repository is private, GitHub asks for your
username and a personal access token (not your password).

```bash
git clone https://github.com/g1n0mag1k/sds-revision-tracker.git
```

```bash
cd sds-revision-tracker
```

```bash
git checkout claude/happy-hamilton-v5uypx
```

Run all later commands from inside this `sds-revision-tracker` folder.

## 4. Install the Python dependencies

[tested in cloud] This creates `.venv/` and installs the pinned packages from
PyPI. It needs internet access once. It does not create data, download
documents or start a server.

```bash
./scripts/bootstrap.sh
```

## 5. Set up the synthetic demonstration

[tested in cloud] Create the database. This never resets an existing database.

```bash
.venv/bin/python -m sdstracker init-db
```

[tested in cloud] Add the synthetic demo data:

- the fictional register entries DEMO-RM-001 and DEMO-RM-002
- a stored synthetic baseline
- synthetic PDFs to upload, written to `data/synthetic_demo/`

If materials already exist, the command does nothing.

```bash
.venv/bin/python -m sdstracker demo-data
```

## 6. Launch the app

[tested in cloud]

```bash
.venv/bin/streamlit run app.py
```

Then open this address in a browser **on the same computer**:

```text
http://localhost:8501
```

The browser does not open automatically. Type your name in the sidebar before
recording actions.

Demo steps:

1. **Intake & material confirmation:** upload
   `data/synthetic_demo/SYNTHETIC_resin-A_v2_2025-06-15.pdf` and click
   **Record receipt**.
2. Select **DEMO-RM-001** and click **Confirm association and classify**.
3. **Comparison, draft & review:** view the classification and the section
   changes, generate the draft, and record the review acknowledgment.

## 7. Stop and restart the app

To stop it, press `Ctrl+C` in the terminal where Streamlit is running.

To restart it, run the launch command again from the `sds-revision-tracker`
folder. Your data in `data/` is kept.

```bash
cd sds-revision-tracker
```

```bash
.venv/bin/streamlit run app.py
```

If port 8501 is already in use, start it on another port and open
`http://localhost:8502` instead:

```bash
.venv/bin/streamlit run app.py --server.port 8502
```

## 8. Download and check the real SDS

The source URL and SHA-256 are recorded in the committed file
`docs/real-sds-provenance.json`. Real PDFs are kept out of Git, and
`samples/real/` is ignored.

[tested in cloud] Print the recorded source URL and hash:

```bash
.venv/bin/python -c "import json; d=json.load(open('docs/real-sds-provenance.json'))['documents'][0]; print(d['source_url']); print(d['sha256'])"
```

[not tested on Zorin] Download it. Alternatively, open the printed URL in your
browser and save the file to the path below.

```bash
mkdir -p samples/real/fisher-acetone-A18-4
```

```bash
curl -L -o samples/real/fisher-acetone-A18-4/fisher_A18-4_acetone_sds.pdf "https://www.fishersci.com/store/msds?partNumber=A184&productDescription=acetone-certified-acs-l&vendorId=VN00033897&keyword=true&countryCode=US&language=en"
```

[tested in cloud] Compare the file with the recorded hash. A match prints `OK`.

```bash
echo "08b3b20730e03106b7867f2376c5bfbee388bcecccb19d61468b70289f1e59bb  samples/real/fisher-acetone-A18-4/fisher_A18-4_acetone_sds.pdf" | sha256sum -c
```

If it prints `FAILED`, the downloaded bytes differ from the recorded file. Do
not assume why. Open the PDF and check its product, supplier, edition and
printed revision date before using it, and record any results as a different
document. If the download is an HTML page instead of a PDF, the supplier site
did not serve the file to `curl`; use your browser instead.

## 9. Initialize the separate real-document data directory

[tested in cloud] `data-real/` is ignored by Git and kept apart from the
synthetic `data/` database.

```bash
SDSTRACKER_DATA_DIR=data-real .venv/bin/python -m sdstracker init-db
```

## 10. Create the material record for the real document

[tested in cloud] The app has no "add material" form; use this existing
command. `REAL-DEMO-001` is a fictional internal code.

```bash
SDSTRACKER_DATA_DIR=data-real .venv/bin/python -m sdstracker add-material --code REAL-DEMO-001 --name "Acetone" --supplier "Fisher Scientific Company" --product-id "A18-4" --cas 67-64-1 --actor "Your name"
```

You can record the receipt now or upload it in the app in step 11.

[tested in cloud]

```bash
SDSTRACKER_DATA_DIR=data-real .venv/bin/python -m sdstracker receive samples/real/fisher-acetone-A18-4/fisher_A18-4_acetone_sds.pdf --actor "Your name"
```

## 11. Launch the app with the real-document data directory

[tested in cloud] Include `SDSTRACKER_DATA_DIR=data-real` every time.
Without it, the app opens the synthetic `data/` database.

```bash
SDSTRACKER_DATA_DIR=data-real .venv/bin/streamlit run app.py
```

Open `http://localhost:8501` on the same computer, then:

1. Type your name in the sidebar.
2. **Intake & material confirmation:** if you did not use `receive`, choose
   the PDF and click **Record receipt**.
3. Check the extracted-fields table: each field shows its status, value, page
   and evidence line.
4. In **Register material**, select
   **REAL-DEMO-001 - Acetone (Fisher Scientific Company)** and click
   **Confirm association and classify**. The expected classification is
   "First document on file".
5. Optionally, on **Materials & documents**, use **Designate baseline**. It
   requires a reason.

## Validation status

- **Synthetic workflow tests:** passed.
- **One real supplier SDS:** checked metadata and supported-section boundaries
  verified on that document after targeted fixes. This is not a measure of
  general extraction accuracy.
- **Genuine old/new revision-pair validation:** not yet run.
