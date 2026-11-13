"""Exercise a deployed verifier using the bundled synthetic modern NIC only."""
import argparse
import os
from tempfile import TemporaryDirectory
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from generate_synthetic_samples import create_synthetic_samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    args = parser.parse_args()
    endpoint = urlsplit(args.base_url)
    if endpoint.scheme != "https" and endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Use HTTPS for a remote deployment.")
    key = os.environ.get("BOOKINGPARTNER_API_KEY")
    if not key:
        parser.error("Set BOOKINGPARTNER_API_KEY in the environment.")
    with TemporaryDirectory() as temp:
        create_synthetic_samples(temp)
        photo = (Path(temp) / "synthetic_smart_card.png").read_bytes()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=90, follow_redirects=False) as client:
        path = "/api/v1/bookingpartner/verify"
        files = {"front_image": ("synthetic.png", photo, "image/png")}
        if client.post(path, files=files).status_code != 401:
            raise SystemExit("Missing-key check failed.")
        response = client.post(
            path, files=files, headers={"X-API-Key": key},
            data={"nic_number": "199518001234", "full_name": "NIMAL SILVA", "dob": "1995-06-29"},
        )
        if response.status_code != 200:
            raise SystemExit(f"Authenticated upload failed with HTTP {response.status_code}.")
        result = response.json()
        if result.get("review_status") not in {"readable", "manual_review"}:
            raise SystemExit("The service could not read the synthetic card.")
        if result.get("match_statuses", {}).get("nic") != "match":
            raise SystemExit("The service did not match the synthetic NIC number.")
        if {"extracted_nic", "extracted_name", "extracted_dob", "matches"} & result.keys():
            raise SystemExit("Response contains private OCR fields.")
        print(f"BookingPartner synthetic upload passed ({result['review_status']}).")
