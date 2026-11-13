# Sri Lankan NIC Document Detection & OCR Verifier (PoC)

> **IMPORTANT DISCLAIMER**  
> This project is an **experimental proof of concept (PoC)** for testing Sri Lankan National Identity Card (NIC) document detection, visual category classification, and OCR extraction.  
> **It is NOT a production or legally certified identity verification system.**  
> Automated OCR results and heuristic classification must **NEVER** be used as sole proof that an identity document is genuine. All final identity decisions must remain with authorized administrative/manual human reviewers.

---

## 🎯 Key Features

1. **Document Detection & Visual Classification**:
   - Detects whether an image shows a Sri Lankan NIC, Not NIC, or Uncertain.
   - Heuristically categorizes into three visual types:
     - **Old Laminated** (pre-2016 blue-violet tinted paper with guilloche security background)
     - **Printed Laminated** (computer-printed light cyan paper)
     - **Newer Plastic Card** (polycarbonate smart card featuring golden contact chip, lion watermark, and bilingual headers)
   - Labeled explicitly as **provisional heuristics**.

2. **Multi-Generation Sri Lankan NIC Number Support**:
   - **Old 9-Digit Format**: `YYDDDSSS[V|X]` (e.g. `853451234V` or `927891234X`).
     - Decodes century birth year (`1900 + YY`).
     - Decodes gender (`day > 500` indicates female, `day <= 500` indicates male).
     - Decodes day-of-year into birth date (`YYYY-MM-DD`).
     - Decodes voter eligibility (`V` for voter, `X` for non-voter).
     - Supports Sri Lankan DRP 366-day leap year convention (February 29th counted for all years with 1-day tolerance).
   - **New 12-Digit Format**: `YYYYDDD0SSSS` (e.g. `198534501234`).
     - Decodes full 4-digit birth year, gender, and day of year.
   - **Cross-Format Equivalence**: Recognizes when an old 9-digit NIC and new 12-digit NIC identify the same identity profile.

3. **Image Quality & Rejection Heuristics**:
   - **Blur Detection**: OpenCV Laplacian variance calculation.
   - **Illumination & Glare**: Mean grayscale brightness and specular reflection detection.
   - **Framing & Aspect Ratio**: Suspected cropping and ID-1 aspect ratio verification.
   - **User Guidance**: Actionable suggestions to retake photos under better lighting/focus.

4. **Local, cross-platform OCR**:
   - PaddleOCR is the default on Linux, with in-process Tesseract fallback.
   - Tesseract loads English, Sinhala, and Tamil. Windows can use its installed OCR profile languages.
   - Unicode block detection for Sinhala (`\u0D80-\u0DFF`) and Tamil (`\u0B80-\u0BFF`).

5. **Field-by-Field Matching**:
   - Name matching with support for Sri Lankan initials (e.g. `K. A. Perera` matching `Kamal Anuradha Perera`).
   - Returns `match`, `partial_match`, `uncertain`, `mismatch`, or `unavailable`.
   - Never guesses on ambiguous Sinhala/Tamil transliterations.

6. **Privacy & Ephemeral Processing**:
   - Local training persists aggregate counts.
   - OCR receives decoded pixels in memory.
   - Application logs omit NIC numbers, names, and dates of birth.
   - Bound to localhost (`127.0.0.1`) with strict CORS restriction.

---

## 📁 Project Structure

```
sri-lanka-nic-verifier/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Application settings, thresholds, CORS
│   │   ├── main.py                # FastAPI entrypoint and API routes
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py         # Pydantic schemas for requests/responses
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── nic_parser.py      # Sri Lankan NIC decoding algorithms
│   │   │   ├── image_quality.py   # OpenCV blur, brightness, glare checks
│   │   │   ├── classifier.py      # Heuristic document classifier
│   │   │   ├── ocr_engine.py      # OCR selection and photo preprocessing
│   │   │   └── matcher.py         # Field-by-field normalization & comparison
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── privacy.py         # PII masking logger
│   ├── tests/
│   │   ├── test_nic_parser.py     # Unit tests for Sri Lankan NIC rules
│   │   ├── test_matcher.py        # Unit tests for name/DOB/NIC matching
│   │   ├── test_image_quality.py  # Unit tests for blur/contrast/rejection
│   │   └── test_api.py            # FastAPI endpoint tests
│   ├── samples/                   # Generated synthetic test images (NO real NICs)
│   ├── generate_synthetic_samples.py # Script generating test cards
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── next.config.mjs
│   ├── src/
│   │   ├── app/
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx           # Verification dashboard
│   │   ├── components/
│   │   │   ├── ImageUploader.tsx  # Drag & drop front/back image upload
│   │   │   ├── OwnerForm.tsx      # Form with live NIC decoding pill
│   │   │   ├── ResultsView.tsx    # Detailed match & signal breakdown
│   │   │   ├── QualityBanner.tsx  # Image quality warnings & retry prompts
│   │   │   └── DisclaimerModal.tsx # Safety & compliance notice modal
│   │   └── lib/
│   │       ├── api.ts             # Typed API client
│   │       └── types.ts           # Shared TypeScript models
└── README.md
```

---

## 🚀 Setup & Running Instructions (Windows)

### Prerequisites
- **Python 3.11+** on Windows with PyWinRT
- **Node.js v18+** and **npm**

---

### Step 1: Backend Setup

1. Open PowerShell or Command Prompt and navigate to `backend`:
   ```powershell
   cd "d:\NIC Test\sri-lanka-nic-verifier\backend"
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install required Python packages:
   ```powershell
   pip install -r requirements.txt
   ```

4. Generate synthetic test card samples (no real NIC photos used):
   ```powershell
   python generate_synthetic_samples.py
   ```
   This creates sample cards in `backend/samples/`:
   - `synthetic_old_laminated.png` (9-digit `853451234V`)
   - `synthetic_printed_laminated.png` (9-digit `927891234X`)
   - `synthetic_smart_card.png` (12-digit `199518001234`)
   - `synthetic_blurry.png` (triggers blur detection)
   - `synthetic_dark.png` (triggers underexposure alert)
   - `synthetic_not_nic.png` (triggers non-NIC rejection)

5. Run the unit test suite:
   ```powershell
   pytest tests/ -v
   ```

6. Start the FastAPI backend server:
   ```powershell
   python run.py
   ```
   The backend will be accessible locally at `http://127.0.0.1:8000`.  
   Interactive API docs are available at `http://127.0.0.1:8000/docs`.

   Keep the backend terminal open while using the frontend. Next.js forwards the
   app's API requests to `http://127.0.0.1:8000`.

### Train your local analysis model

Analyze the photo, check the NIC number or full name against the card, then
select **Save training feedback**. The app learns which preprocessing option
reads each field more accurately on photos with similar quality. The SQLite file at
`%LOCALAPPDATA%\SriLankaNICVerifier\analysis.sqlite3` holds aggregate counts.
Pending OCR number and name candidates stay in memory and are eligible for feedback for
up to 15 minutes. All OCR inference runs locally.

### Select an OCR backend

Set `OCR_BACKEND` in the environment or backend `.env`.

| Value | Behavior |
| --- | --- |
| `auto` | In-process Windows OCR on Windows, PaddleOCR with Tesseract fallback on Linux |
| `paddle` | PaddleOCR PP-OCRv5 English on CPU. Falls back to Tesseract if initialization or inference fails, or if it returns no text. |
| `tesseract` | Tesseract with `eng+sin+tam` |
| `windows` | Windows only, using WinRT and the Windows profile's installed OCR languages |

For Linux on Debian, install `libtesseract-dev`, `libleptonica-dev`,
`tesseract-ocr-eng`, `tesseract-ocr-sin`, and `tesseract-ocr-tam`. Then run
`python -m pip install -r requirements-ocr.txt` in the backend environment.
Set `TESSDATA_PREFIX` to the directory containing the three `.traineddata`
files if Tesseract cannot locate them. PaddleOCR prepares its weights on first
initialization and may download them to its model cache. Warm it using a
synthetic upload before serving traffic. Docker packaging comes in Phase 5.

The OCR service loads each backend once per process. It reports per-line scores
when the backend exposes them. Windows OCR reports unknown scores, and the app
flags OCR with low or unknown confidence for manual review.

### NIC number field OCR

The verifier reads the expected number region on the selected card orientation
using the original and enhanced crop. Tesseract applies a digits and V/X
whitelist first. PaddleOCR and Windows OCR constrain the result after decoding.
A crop read can correct common look-alike letters in digit positions, and each
candidate must pass the NIC parser. A valid full-card read takes precedence
when the crop disagrees. The local review UI displays alternate reads, and
BookingPartner receives a manual-review warning without the raw numbers.

### Optional trained vision models

The verifier can use YOLO for card and field crops and MobileNetV3-Small for
card type. Install `backend/requirements-vision.txt` and follow the
[private dataset and training guide](backend/dataset/README.md).
Set `NIC_DETECTOR_WEIGHTS` and `NIC_CLASSIFIER_WEIGHTS` to trusted local
checkpoints. The heuristic pipeline remains available without usable weights.

### BookingPartner integration on AWS

1. Set up the Linux OCR dependencies above on your test instance. Run OCR on
   a synthetic NIC with the same backend and runtime that will serve requests.
2. Run FastAPI as a service without reload. Keep port 8000 private and put it
   behind an HTTPS endpoint reachable by BookingPartner's backend. If both run
   in the same VPC, use an internal HTTPS endpoint and restrict ingress to
   BookingPartner's service. Keep the learned SQLite file on encrypted EBS.
3. Generate a key with `python -c "import secrets; print(secrets.token_hex(32))"`.
   Store it in AWS Secrets Manager and give each service access through its
   runtime role. Set `BOOKINGPARTNER_API_KEY` in the verifier's environment.
   Setting the key enables the BookingPartner endpoint and disables local
   upload and training routes on that instance. Continue training on your
   local installation.
4. In a Node.js BookingPartner backend, install `lanka-validations` and use
   `isValidNic` for typed NIC numbers. Send photos from the authenticated
   BookingPartner backend to FastAPI. Keep the key out of browser code and
   avoid logging request bodies, keys, or full OCR results.

```ts
import { isValidNic } from 'lanka-validations/nic';

export async function analyzeNIC(front: File, typedNIC?: string, back?: File) {
  if (typedNIC && !isValidNic(typedNIC)) {
    throw new Error('Enter a valid Sri Lankan NIC number.');
  }
  const url = new URL('/api/v1/bookingpartner/verify', process.env.NIC_API_URL);
  const key = process.env.BOOKINGPARTNER_API_KEY;
  if (url.protocol !== 'https:' || !key) throw new Error('Configure the NIC service.');

  const form = new FormData();
  form.set('front_image', front);
  if (back) form.set('back_image', back);
  if (typedNIC) form.set('nic_number', typedNIC);
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'X-API-Key': key },
    body: form,
    redirect: 'error',
    signal: AbortSignal.timeout(90000),
  });
  if (!response.ok) throw new Error(`NIC service returned HTTP ${response.status}.`);
  return response.json();
}
```

Use the API's matching and image-quality results to support manual review.
Use `review_status` for the next action in the booking flow. `readable` means
the image yielded usable text, `retake_needed` calls for a clearer photo, and
`manual_review` flags incomplete or conflicting evidence.
Restrict the BookingPartner upload route to authorized users, limit uploads
to 10 MB per image, and return only the fields needed for the booking flow.

The BookingPartner response contains the request ID, review status, date source,
and field warnings. During key rotation, set `BOOKINGPARTNER_PREVIOUS_API_KEY`
to the outgoing key, deploy the new primary key, update BookingPartner, then
remove the outgoing key. Use `Idempotency-Key` with a unique value per upload
attempt to prevent concurrent duplicates. The default limit is 20 uploads per
minute per verifier process. Configure the HTTPS gateway to enforce a total
request body limit and a shared rate limit if running multiple workers.

From the backend directory, run
`python smoke_bookingpartner.py https://your-verifier-host` with the API key
in the environment. The command uploads only the bundled synthetic card and
checks authorization, OCR usability, and response privacy.

### Measure OCR accuracy locally

Keep a private JSON manifest outside source control. Each row has a front photo
path relative to the manifest, a card group, a split, and the fields you can
verify directly against that card. Use the same group and split for every
rotation, crop, or enhanced copy of a card. Reserve the test split before
saving any training feedback.

```json
[
  {
    "front": "photos/synthetic-front.png",
    "card_group": "synthetic-001",
    "split": "test",
    "cohort": "modern",
    "nic": "199518001234",
    "name": "Nimal Silva"
  }
]
```

Run `python evaluate_ocr.py PATH_TO_MANIFEST` from the backend folder.
The report contains correct, wrong, and unread counts per field and cohort.
Set `printed_dob` only when the birth date is visible on the front photo.

---

### Step 2: Frontend Setup

1. Open a new PowerShell terminal and navigate to `frontend`:
   ```powershell
   cd "d:\NIC Test\sri-lanka-nic-verifier\frontend"
   ```

2. Install npm dependencies:
   ```powershell
   npm install
   ```

3. Run the Next.js development server:
   ```powershell
   npm run dev
   ```

4. Open your browser and navigate to:
   ```
   http://127.0.0.1:3000
   ```

---

## 🧪 Testing Scenarios

1. **Old 9-Digit NIC Test**:
   - Upload `backend/samples/synthetic_old_laminated.png`.
   - Click "Old 9-Digit" preset or enter:
     - Name: `K. A. Perera`
     - NIC: `853451234V`
     - DOB: `1985-12-11`
   - Observe: Image classified as *Old Laminated*, NIC decoded as Male / Year 1985 / Voter, all fields match.

2. **Smart Card 12-Digit NIC Test**:
   - Upload `backend/samples/synthetic_smart_card.png`.
   - Click "New 12-Digit" preset or enter:
     - Name: `Nimal Silva`
     - NIC: `199518001234`
     - DOB: `1995-06-29`
   - Observe: Image classified as *Newer Plastic Card (Smart Card with Chip)*, all fields match.

3. **Blurry Image Rejection**:
   - Upload `backend/samples/synthetic_blurry.png`.
   - Observe: Quality banner warns *Sharpness: Blurry* and requests re-upload.

4. **Dark Image Rejection**:
   - Upload `backend/samples/synthetic_dark.png`.
   - Observe: Quality banner warns *Lighting: Too Dark* and provides capture advice.

5. **Random Image Rejection**:
   - Upload `backend/samples/synthetic_not_nic.png`.
   - Observe: Classified as *Not a Sri Lankan NIC* and rejected.

---

## 🔒 Privacy & Security Design
- **Localhost Bound**: API listens on `127.0.0.1` and CORS only permits `localhost:3000`.
- **Application Logs**: Request IDs are logged without NIC numbers or names.
- **In-memory Images**: Multipart uploads and decoded OCR pixels stay in memory.
  Keep the API private behind a gateway with a request-body limit.
- **Human Authority**: All automated scores are explicitly marked as provisional and require human verification.
