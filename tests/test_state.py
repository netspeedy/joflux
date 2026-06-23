"""Migration state tests."""

from pathlib import Path

from joflux.state import MigrationState


def test_state_writes_inventory_and_logs(tmp_path: Path) -> None:
    """Inventory and append-only logs are persisted as JSON."""
    state = MigrationState(str(tmp_path))

    state.save_inventory([{"name": "example", "private": False}])
    state.log_migration("example", "initiated", "started", 123)
    state.log_status("example", "completed")
    state.log_verification("example", "verified", "size:1")
    state.log_archive("example", "success", "archived")

    assert state.load_inventory()[0]["name"] == "example"
    assert state.load_json(state.migration_log)[0]["migration_id"] == 123
    assert state.load_json(state.status_file)[0]["status"] == "completed"
    assert state.load_json(state.verify_file)[0]["details"] == "size:1"
    assert state.load_json(state.archive_log)[0]["message"] == "archived"
