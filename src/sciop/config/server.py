from typing import Literal

from pydantic import BaseModel, Field


class CSPConfig(BaseModel):
    """
    Configure CSP headers used by the csp_headers middleware

    For now these are single-valued params, expand the annotations as needed.
    """

    default_src: Literal["self"] | str = "self"
    child_src: Literal["self"] | str = "self"
    img_src: Literal["self"] | str = "'self' data:"
    object_src: Literal["none"] | str = "none"
    script_src: Literal["self"] | str = "strict-dynamic"  # "strict-dynamic"
    style_src: Literal["self"] | str = "self"
    font_src: Literal["self"] | str = "self"

    nonce_entropy: int = 90
    enable_nonce: list[str] = Field(default_factory=lambda: ["script_src"])

    def format(self, nonce: str) -> str:
        """
        Create a Content-Security_Policy header string

        TODO: This seems rly slow on every page load, profile this later.
        """

        format_parts = []
        for key, val in self.model_dump().items():
            if key in ("nonce_entropy", "enable_nonce"):
                continue

            # if we're given a pre-quoted string, or multiple params, assume they're quoted already
            if "'" not in val:
                val = f"'{val}'"

            if key in self.enable_nonce:
                val = f"'nonce-{nonce}' {val}"

            key = key.replace("_", "-")
            format_parts.append(f"{key} {val}")

        return "; ".join(format_parts)


class ServerConfig(BaseModel):
    """
    Configuration for the server itself - how and from where content is served.
    """

    base_url: str = "http://localhost:8000"
    """
    Root URL where the site is hosted and can be accessed externally.

    This is used when building URLs for elements of the site and its metadata.
    In development, this is usually localhost:{port}.
    In production, this should be the full URL, including protocol,
    of the domain.

    Note: Hosting sciop in a path beneath the domain root is currently unsupported 
    due to the use of relative paths in templates, but this will be fixed and PRs are welcome.
    """
    host: str = "localhost"
    """Host portion of url"""
    port: int = 8000
    """Port where local service should serve from"""
    csp: CSPConfig = CSPConfig()
    """Submodel containing CSP config"""
