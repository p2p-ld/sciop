from importlib.metadata import version
from typing import Literal

from pydantic import BaseModel, Field

try:
    sciop_version = version("sciop")
except Exception:
    sciop_version = "0.0.0"


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
    user_agent: str = f"sciop ({sciop_version})"
    """User agent to use for outgoing http requests"""
    scheduler_mode: Literal["local", "rpc"] = "rpc"
    """
    Scheduler can be run either...
    
    - `local`: as a module-level instance within one worker,
      jobs cannot be queued after sciop has started up (e.g. with add_queue_job)
    - `rpc`: as a separate process with an xmlrpc proxy.
      all workers have access to exposed scheduler methods, and thus can queue jobs after startup
      
    in both cases, the public functions in the scheduler module should be used rather than
    directly interacting with the scheduler object.
    """
    scheduler_rpc_port: int = 8011
    """Port to expose (locally) when running """
