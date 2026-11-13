import re
import logging
from typing import Optional

def mask_nic(nic: Optional[str]) -> str:
    """Mask NIC number preserving only format prefix and suffix.
    E.g. 853451234V -> 85*****34V, 198534501234 -> 1985******34
    """
    if not nic or not isinstance(nic, str):
        return "[EMPTY]"
    clean = nic.strip().upper()
    if len(clean) == 10:  # Old format 9 digits + letter
        return f"{clean[:2]}*****{clean[-3:]}"
    elif len(clean) == 12:  # New format 12 digits
        return f"{clean[:4]}******{clean[-2:]}"
    elif len(clean) > 4:
        return f"{clean[:2]}***{clean[-2:]}"
    return "***"

def mask_name(name: Optional[str]) -> str:
    """Mask name preserving first initial of tokens."""
    if not name or not isinstance(name, str):
        return "[EMPTY]"
    parts = name.strip().split()
    masked = [f"{p[0]}***" if len(p) > 1 else p for p in parts]
    return " ".join(masked)

def mask_dob(dob: Optional[str]) -> str:
    """Mask DOB preserving only year."""
    if not dob or not isinstance(dob, str):
        return "[EMPTY]"
    m = re.match(r"^(\d{4})", dob.strip())
    if m:
        return f"{m.group(1)}-**-**"
    return "****-**-**"

class MaskingFormatter(logging.Formatter):
    """Logging formatter that redacts unmasked NIC numbers."""
    OLD_NIC_REGEX = re.compile(r"\b([0-9]{2})[0-9]{7}([vVxX])\b")
    NEW_NIC_REGEX = re.compile(r"\b([0-9]{4})[0-9]{6}([0-9]{2})\b")

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        msg = self.OLD_NIC_REGEX.sub(r"\1*****\2", msg)
        msg = self.NEW_NIC_REGEX.sub(r"\1******\2", msg)
        return msg

def get_sanitized_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = MaskingFormatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
