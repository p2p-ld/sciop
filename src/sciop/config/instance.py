from functools import cached_property
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class InstanceRule(BaseModel):
    title: str
    description: str


class InstanceQuote(BaseModel):
    content: str
    attribution: str
    link_text: str
    link: str


class InstanceConfig(BaseModel):
    """
    Configuration for the public-facing parts of this instance
    """

    contact_email: Optional[EmailStr] = Field(
        default=None, description="Email to list as contact in page footer"
    )
    quotes: list[InstanceQuote] = Field(
        description="A list of quotes to show on the homepage",
        default_factory=list,
    )
    rules: list[InstanceRule] = Field(
        default_factory=list, description="Site rules to display in the docs"
    )
    footer: str = Field(
        "",
        description="Footer message shown on the bottom-right of every page."
        "Markdown is supported.",
    )
    alert: str | None = Field(
        None,
        description="An alert banner that is shown beneath the header of the page. "
        "Used for temporary notifications and updates. "
        "Markdown is supported.",
    )
    show_docs: bool = Field(
        True,
        description="Show link to documentation in navigation. "
        "If `True`, the docs should either be prebuilt and present in the "
        "[.paths.docs][sciop.config.paths.PathConfig.docs] directory, "
        "or the [.services.docs][sciop.config.services.DocsConfig] auto-build "
        "service should be enabled.",
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

    @cached_property
    def alert_html(self) -> str | None:
        if self.alert is None:
            return None

        from sciop.services.markdown import render_markdown

        return render_markdown(self.alert)
