"""Runtime Executions API."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sinas.client import SinasClient


class ExecutionsAPI:
    """Runtime Executions API methods."""

    def __init__(self, client: "SinasClient") -> None:
        self._client = client

    def list(
        self,
        function_name: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List function executions.

        Args:
            function_name: Filter by function name.
            status: Filter by execution status (running, completed, failed, awaiting_input).
            skip: Number of executions to skip (pagination).
            limit: Maximum number of executions to return (1-1000).

        Returns:
            List of executions.
        """
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if function_name is not None:
            params["function_name"] = function_name
        if status is not None:
            params["status"] = status

        return self._client._request("GET", "/executions", params=params)

    def get(self, execution_id: str) -> Dict[str, Any]:
        """Get a specific execution.

        Args:
            execution_id: Execution ID.

        Returns:
            Execution details.
        """
        return self._client._request("GET", f"/executions/{execution_id}")

    def get_steps(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all steps for an execution.

        Args:
            execution_id: Execution ID.

        Returns:
            List of execution steps.
        """
        return self._client._request("GET", f"/executions/{execution_id}/steps")

    def continue_execution(
        self,
        execution_id: str,
        input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Continue a paused execution with user input.

        Args:
            execution_id: Execution ID.
            input: User input data.

        Returns:
            Continuation response with execution status, output_data, or next prompt.
        """
        return self._client._request(
            "POST",
            f"/executions/{execution_id}/continue",
            json={"input": input}
        )
