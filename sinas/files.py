"""Runtime Files API."""

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class FilesAPI:
    """Runtime Files API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def upload(
        self,
        namespace: str,
        collection: str,
        name: str,
        content_base64: str,
        content_type: str,
        visibility: str = "private",
        file_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload a file.

        Args:
            namespace: File namespace.
            collection: File collection.
            name: Filename.
            content_base64: Base64-encoded file content.
            content_type: MIME type of the file.
            visibility: Visibility level ("private", "group", "public"). Defaults to "private".
            file_metadata: Optional metadata dict to attach to the file.

        Returns:
            File info.
        """
        data: Dict[str, Any] = {
            "name": name,
            "content_base64": content_base64,
            "content_type": content_type,
            "visibility": visibility,
        }
        if file_metadata is not None:
            data["file_metadata"] = file_metadata

        return self._client._request("POST", f"/files/{namespace}/{collection}", json=data)

    def upload_bytes(
        self,
        namespace: str,
        collection: str,
        name: str,
        content: bytes,
        content_type: str,
        visibility: str = "private",
        file_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload a file from bytes.

        Convenience method that base64-encodes the content and calls upload().

        Args:
            namespace: File namespace.
            collection: File collection.
            name: Filename.
            content: Raw file content as bytes.
            content_type: MIME type of the file.
            visibility: Visibility level. Defaults to "private".
            file_metadata: Optional metadata dict.

        Returns:
            File info.
        """
        content_base64 = base64.b64encode(content).decode("utf-8")
        return self.upload(
            namespace=namespace,
            collection=collection,
            name=name,
            content_base64=content_base64,
            content_type=content_type,
            visibility=visibility,
            file_metadata=file_metadata,
        )

    def upload_from_path(
        self,
        namespace: str,
        collection: str,
        file_path: str,
        name: Optional[str] = None,
        content_type: Optional[str] = None,
        visibility: str = "private",
        file_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Upload a file from a local file path.

        Convenience method that reads the file, guesses the MIME type, and calls upload_bytes().

        Args:
            namespace: File namespace.
            collection: File collection.
            file_path: Path to the local file.
            name: Filename. Defaults to the file's name.
            content_type: MIME type. Guessed from file extension if not provided.
            visibility: Visibility level. Defaults to "private".
            file_metadata: Optional metadata dict.

        Returns:
            File info.
        """
        path = Path(file_path)
        content = path.read_bytes()
        if name is None:
            name = path.name
        if content_type is None:
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return self.upload_bytes(
            namespace=namespace,
            collection=collection,
            name=name,
            content=content,
            content_type=content_type,
            visibility=visibility,
            file_metadata=file_metadata,
        )

    def download(
        self,
        namespace: str,
        collection: str,
        filename: str,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Download a file.

        Args:
            namespace: File namespace.
            collection: File collection.
            filename: Name of the file to download.
            version: Optional specific version to download.

        Returns:
            Dict with content_base64, content_type, file_metadata, and version.
        """
        params: Dict[str, Any] = {}
        if version is not None:
            params["version"] = version

        return self._client._request(
            "GET", f"/files/{namespace}/{collection}/{filename}", params=params or None
        )

    def download_bytes(
        self,
        namespace: str,
        collection: str,
        filename: str,
        version: Optional[int] = None,
    ) -> bytes:
        """Download a file and return raw bytes.

        Convenience method that downloads and base64-decodes the content.

        Args:
            namespace: File namespace.
            collection: File collection.
            filename: Name of the file to download.
            version: Optional specific version to download.

        Returns:
            Raw file content as bytes.
        """
        result = self.download(
            namespace=namespace,
            collection=collection,
            filename=filename,
            version=version,
        )
        return base64.b64decode(result["content_base64"])

    def list(
        self,
        namespace: str,
        collection: str,
    ) -> List[Dict[str, Any]]:
        """List files in a collection.

        Args:
            namespace: File namespace.
            collection: File collection.

        Returns:
            List of files with version history.
        """
        return self._client._request("GET", f"/files/{namespace}/{collection}")

    def search(
        self,
        namespace: str,
        collection: str,
        query: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search files in a collection.

        Args:
            namespace: File namespace.
            collection: File collection.
            query: Optional regex search query for filenames.
            metadata_filter: Optional metadata filter dict.
            limit: Maximum number of results. Defaults to 100.

        Returns:
            List of matching files.
        """
        data: Dict[str, Any] = {"limit": limit}
        if query is not None:
            data["query"] = query
        if metadata_filter is not None:
            data["metadata_filter"] = metadata_filter

        return self._client._request(
            "POST", f"/files/{namespace}/{collection}/search", json=data
        )

    def update_metadata(
        self,
        namespace: str,
        collection: str,
        filename: str,
        file_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update file metadata.

        Args:
            namespace: File namespace.
            collection: File collection.
            filename: Name of the file.
            file_metadata: New metadata dict.

        Returns:
            Updated file info.
        """
        return self._client._request(
            "PATCH",
            f"/files/{namespace}/{collection}/{filename}",
            json={"file_metadata": file_metadata},
        )

    def generate_temp_url(
        self,
        namespace: str,
        collection: str,
        filename: str,
        version: Optional[int] = None,
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """Generate a temporary public URL for a file.

        The URL is signed and does not require authentication to access.

        Args:
            namespace: File namespace.
            collection: File collection.
            filename: Name of the file.
            version: Optional specific version. Defaults to current version.
            expires_in: URL expiry time in seconds (60-86400). Defaults to 3600 (1 hour).

        Returns:
            Dict with url, filename, content_type, version, and expires_in.
        """
        params: Dict[str, Any] = {}
        if version is not None:
            params["version"] = version
        if expires_in != 3600:
            params["expires_in"] = expires_in

        return self._client._request(
            "POST",
            f"/files/{namespace}/{collection}/{filename}/url",
            params=params or None,
        )

    def delete(
        self,
        namespace: str,
        collection: str,
        filename: str,
    ) -> None:
        """Delete a file.

        Args:
            namespace: File namespace.
            collection: File collection.
            filename: Name of the file to delete.

        Returns:
            None.
        """
        return self._client._request(
            "DELETE", f"/files/{namespace}/{collection}/{filename}"
        )

    def serve(self, token: str) -> Dict[str, Any]:
        """Serve a file by token (unauthenticated).

        Args:
            token: File serve token.

        Returns:
            Dict with content (bytes), content_type (str), and filename (str).
        """
        url = f"{self._client.base_url}/files/serve/{token}"
        response = self._client._client.request(method="GET", url=url)
        self._client._handle_response(response)

        content_type = response.headers.get("content-type", "application/octet-stream")
        content_disposition = response.headers.get("content-disposition", "")
        filename = ""
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[-1].strip('"')

        return {
            "content": response.content,
            "content_type": content_type,
            "filename": filename,
        }
