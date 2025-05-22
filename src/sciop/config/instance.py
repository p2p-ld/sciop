from functools import cached_property
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class InstanceRule(BaseModel):
    title: str
    description: str


class InstanceConfig(BaseModel):
    """
    Configuration for the public-facing parts of this instance
    """

    contact_email: Optional[EmailStr] = Field(
        default=None, description="Email to list as contact in page footer"
    )
    rules: list[InstanceRule] = Field(
        default_factory=list, description="Site rules to display in the docs"
    )
    footer: str = Field(
        "",
        description="Footer message shown on the bottom-right of every page."
        "Markdown is supported.",
    )

    @property
    def contact_email_obfuscated(self) -> str | None:
        """Email address like `user [at] domain (dot) tld"""
        if self.contact_email is None:
            return None
        user, domain = self.contact_email.split("@")
        domain, tld = domain.rsplit(".", 1)
        return f"{user} [at] {domain} (dot) {tld}"

    @cached_property
    def footer_html(self) -> str:
        from sciop.services.markdown import render_markdown

        return render_markdown(self.footer)
