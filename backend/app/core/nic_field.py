"""Read and validate candidates from a dedicated NIC number crop."""

import re

from .nic_parser import parse_sri_lankan_nic

NIC_ALPHABET = "0123456789VXvx"
CONFUSIONS = str.maketrans({"O": "0", "I": "1", "l": "1", "S": "5", "B": "8"})


def normalize_nic_field(text: str) -> str | None:
    # Only strip known labels and spacing inside the field. Never join arbitrary
    # card text or repair characters in a legacy suffix.
    value = re.sub(r"^\s*(?:NIC(?:\s+NO\.?|\s+NUMBER)?|NO\.)\s*:\s*", "", text, flags=re.I)
    value = "".join(value.split())
    if re.fullmatch(r"[0-9OIlSB]{9}[VvXx]", value):
        candidate = value[:-1].translate(CONFUSIONS) + value[-1].upper()
    elif re.fullmatch(r"[0-9OIlSB]{12}", value):
        candidate = value.translate(CONFUSIONS)
    else:
        return None
    return candidate if parse_sri_lankan_nic(candidate).is_valid else None
