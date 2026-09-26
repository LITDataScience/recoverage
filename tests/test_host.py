from recoverage.host import HostBudget, TempSpaceError, assert_temp_space

_GB = 1024 ** 3


def test_baseline_matches_the_historical_caps():
    budget = HostBudget.baseline()
    assert budget.walk_files == 20_000
    assert budget.walk_bytes == 200_000_000
    assert budget.file_bytes == 1_000_000
    assert budget.cache_bytes == 64_000_000
    assert budget.run_budget_s == 600
    assert budget.coverage_timeout_s == 180
    assert budget.parse_workers == 1
    assert budget.allow_deep is True
    assert budget.temp_ok is True


def test_two_gigabytes_skips_deep_probes_and_halves_the_caps():
    budget = HostBudget.for_machine(cpu=2, ram_bytes=2 * _GB - 1, free_temp_bytes=10 * _GB)
    assert budget.allow_deep is False
    assert budget.walk_files == 10_000
    assert budget.walk_bytes == 100_000_000
    assert budget.cache_bytes == 32_000_000
    assert budget.run_budget_s == 300
    assert "under 2 GB" in budget.note


def test_four_gigabytes_stays_on_the_baseline():
    budget = HostBudget.for_machine(cpu=4, ram_bytes=4 * _GB, free_temp_bytes=10 * _GB)
    assert budget.walk_files == 20_000
    assert budget.allow_deep is True
    assert budget.parse_workers == 1
    assert "Baseline caps" in budget.note


def test_sixteen_gigabytes_and_eight_cores_raise_the_cap():
    budget = HostBudget.for_machine(cpu=12, ram_bytes=16 * _GB, free_temp_bytes=10 * _GB)
    assert budget.walk_files == 40_000
    assert budget.cache_bytes == 128_000_000
    assert budget.parse_workers == 8
    assert budget.run_budget_s == 600


def test_a_full_temp_volume_refuses_copies():
    budget = HostBudget.for_machine(cpu=4, ram_bytes=8 * _GB, free_temp_bytes=500_000_000)
    assert budget.temp_ok is False
    assert "under 1 GB" in budget.note
    try:
        assert_temp_space(budget)
    except TempSpaceError as exc:
        assert "under 1 GB" in str(exc)
    else:
        raise AssertionError("temp copy was allowed")


def test_baseline_env_ignores_the_machine(monkeypatch):
    monkeypatch.setenv("RECOVERAGE_BUDGET", "baseline")
    assert HostBudget.detect() == HostBudget.baseline()
