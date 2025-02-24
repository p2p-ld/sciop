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
