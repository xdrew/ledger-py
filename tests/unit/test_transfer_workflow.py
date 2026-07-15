"""Unit tests for the workflow's query surface and failure mapping."""

from ledger.temporal.workflows.transfer_workflow import TransferWorkflow


class TestWorkflowQueries:
    def test_initial_status_and_no_failure(self) -> None:
        workflow = TransferWorkflow()
        assert workflow.current_status() == "initiated"
        assert workflow.failure_reason() is None
