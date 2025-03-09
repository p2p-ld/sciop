import importlib.resources

TEMPLATE_DIR = importlib.resources.files("sciop") / "templates"
STATIC_DIR = importlib.resources.files("sciop") / "static"
DOCS_DIR = importlib.resources.files("sciop") / "docs"

COMMON_RESERVED_SLUGS = (
    "index",
    "partial",
    "parts",
    "uploads",
    "upload",
    "claim" "downloads",
    "download",
    "search",
)

DATASET_RESERVED_SLUGS = (*COMMON_RESERVED_SLUGS,)

DATASET_PART_RESERVED_SLUGS = (*COMMON_RESERVED_SLUGS,)
"""
To avoid conflicting with frontend routes, forbid these slugs for dataset parts
"""

PREFIX_LEN = len("abcdefg-REM__")
"""
The length of a uniqueness-dodging prefix used when removing a dataset or upload,
a 6-character hash of the created_at timestamp, and a 3-letter key.

DB tables are expanded by this length, larger than the creation validators
"""
