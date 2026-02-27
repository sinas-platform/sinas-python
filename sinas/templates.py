"""Runtime Templates API."""

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class TemplatesAPI:
    """Runtime Templates API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def render(
        self, namespace: str, name: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Render a template with given variables.

        Args:
            namespace: Template namespace.
            name: Template name.
            variables: Variables to use in template rendering.

        Returns:
            Rendered template with title, html_content, and text_content.
            Example: {
                "title": "Welcome to SINAS",
                "html_content": "<html>...</html>",
                "text_content": "Welcome..."
            }
        """
        return self._client._request(
            "POST",
            f"/templates/{namespace}/{name}/render",
            json={"variables": variables},
        )

    def send_email(
        self,
        namespace: str,
        name: str,
        to: str,
        variables: Dict[str, Any],
        from_alias: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email using a template.

        Args:
            namespace: Template namespace.
            name: Template name.
            to: Recipient email address.
            variables: Variables to use in template rendering.
            from_alias: Email alias (e.g., "support" -> support@domain.com).
            from_name: Display name for sender (e.g., "SINAS Support").

        Returns:
            Response with message and recipient.
            Example: {"message": "Email sent successfully", "to": "user@example.com"}
        """
        payload: Dict[str, Any] = {
            "to": to,
            "variables": variables,
        }
        if from_alias:
            payload["from_alias"] = from_alias
        if from_name:
            payload["from_name"] = from_name

        return self._client._request(
            "POST",
            f"/templates/{namespace}/{name}/email",
            json=payload,
        )
