from pathlib import Path

import pytest

from tc1d.gui.config import (
    default_config,
    dump_yaml,
    load_yaml_file,
    normalize_config,
    parse_entry_value,
    parse_yaml_text,
    validate_config,
)


def test_default_config_generates_valid_forward_yaml():
    config = normalize_config(default_config())

    assert config["general"]["run_type"] == "forward"
    assert config["general"]["batch_mode"] is False
    assert config["general"]["inverse_mode"] is False
    assert validate_config(config) == []

    yaml_text = dump_yaml(config)
    reparsed = parse_yaml_text(yaml_text)
    assert reparsed["geometry_time"]["length"] == 125.0
    assert reparsed["output"]["save_plots"] is True


def test_import_sample_yaml_round_trips_key_sections():
    sample = Path(__file__).parents[1] / "data" / "input_file.yaml"
    config = load_yaml_file(sample)

    assert config["general"]["run_type"] == "mcmc"
    assert config["general"]["inverse_mode"] is True
    assert config["erosion_model"]["ero_type"] == 0
    assert len(config["erosion_model"]["ero_stages"]) == 3

    reparsed = parse_yaml_text(dump_yaml(config))
    assert reparsed["inversion"]["mcmc"]["mcmc_nsteps"] == 300


@pytest.mark.parametrize("run_type", ["na", "mcmc"])
def test_inverse_run_types_force_inverse_mode(run_type):
    config = default_config()
    config["general"]["run_type"] = run_type
    config["general"]["inverse_mode"] = False

    normalized = normalize_config(config)

    assert normalized["general"]["inverse_mode"] is True
    assert validate_config(normalized) == []


def test_erosion_type_zero_requires_stages():
    config = default_config()
    config["erosion_model"]["ero_type"] = 0

    errors = validate_config(normalize_config(config))

    assert any("requires at least one erosion stage" in error for error in errors)


def test_range_fields_parse_as_lists():
    assert parse_entry_value("0.0, 20.0", float) == [0.0, 20.0]
    assert parse_entry_value("[1, 5]", int) == [1, 5]
    assert parse_entry_value("10", float) == 10.0


def test_scalar_only_fields_reject_lists():
    config = default_config()
    config["observations"]["misfit_type"] = [1, 2]
    config["inversion"]["mcmc"]["mcmc_nwalkers"] = [8, 16]

    errors = validate_config(normalize_config(config))

    assert any("misfit_type" in error for error in errors)
    assert any("mcmc_nwalkers" in error for error in errors)
