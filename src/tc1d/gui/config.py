"""YAML configuration helpers for the Tc1D desktop GUI.

This module keeps GUI state close to the existing Tc1D YAML format. The GUI can
import a partial config, fill in omitted defaults, edit it through form fields,
and export a config that the existing CLI understands.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import yaml


RUN_TYPES = ("forward", "batch", "na", "mcmc")
EROSION_STAGE_TYPES = ("constant", "linear", "exponential")
EROSION_STAGE_UNITS = ("erosion_rate", "thickness")

# Fields the Tc1D CLI reads as bare scalars (not nargs="+"), so a range/list
# entered in the GUI (e.g. "1, 2") would crash the model when cast with
# int()/float(). These are rejected during validation. Section uses dotted
# notation to reach nested inversion settings.
SCALAR_ONLY_FIELDS: tuple[tuple[str, str], ...] = (
    ("age_prediction", "madtrax_aft_kinetic_model"),
    ("age_prediction", "madtrax_zft_kinetic_model"),
    ("age_prediction", "past_age_increment"),
    ("plotting", "mantle_solidus_xoh"),
    ("observations", "misfit_num_params"),
    ("observations", "misfit_type"),
    ("inversion.neighbourhood_algorithm", "na_ns"),
    ("inversion.neighbourhood_algorithm", "na_nr"),
    ("inversion.neighbourhood_algorithm", "na_ni"),
    ("inversion.neighbourhood_algorithm", "na_n"),
    ("inversion.neighbourhood_algorithm", "na_n_resample"),
    ("inversion.neighbourhood_algorithm", "na_n_walkers"),
    ("inversion.mcmc", "mcmc_nwalkers"),
    ("inversion.mcmc", "mcmc_nsteps"),
    ("inversion.mcmc", "mcmc_discard"),
    ("inversion.mcmc", "mcmc_thin"),
)


# These defaults mirror the CLI defaults closely enough for a fresh GUI launch.
# Imported YAML is merged into this mapping so partial configs still produce a
# complete form and preview.
DEFAULT_CONFIG: dict[str, Any] = {
    "general": {
        "run_type": "forward",
        "batch_mode": False,
        "inverse_mode": False,
        "debug": False,
        "echo_inputs": False,
        "no_echo_info": False,
        "no_echo_thermal_info": False,
        "no_echo_ages": False,
    },
    "geometry_time": {
        "length": 125.0,
        "nx": 251,
        "time": 50.0,
        "dt": 5000.0,
        "init_moho_depth": 50.0,
        "crustal_uplift": False,
        "fixed_moho": False,
        "removal_fraction": 0.0,
        "removal_start_time": 0.0,
        "removal_end_time": -1.0,
    },
    "materials": {
        "rho_crust": 2850.0,
        "cp_crust": 800.0,
        "k_crust": 2.75,
        "heat_prod_crust": 0.5,
        "heat_prod_decay_depth": -1.0,
        "alphav_crust": 3.0e-5,
        "rho_mantle": 3250.0,
        "cp_mantle": 1000.0,
        "k_mantle": 2.5,
        "heat_prod_mantle": 0.0,
        "alphav_mantle": 3.0e-5,
        "rho_a": 3250.0,
        "k_a": 20.0,
    },
    "thermal_model": {
        "explicit": False,
        "mantle_adiabat": True,
        "temp_surf": 0.0,
        "temp_base": 1300.0,
    },
    "intrusion_model": {
        "intrusion_temperature": 750.0,
        "intrusion_start_time": -1.0,
        "intrusion_duration": -1.0,
        "intrusion_thickness": -1.0,
        "intrusion_base_depth": -1.0,
    },
    "erosion_model": {
        "vx_init": 0.0,
        "ero_type": 1,
        "ero_option1": 0.0,
        "ero_option2": 0.0,
        "ero_option3": 0.0,
        "ero_option4": 0.0,
        "ero_option5": 0.0,
        "ero_option6": 0.0,
        "ero_option7": 0.0,
        "ero_option8": 0.0,
        "ero_option9": 0.0,
        "ero_option10": 0.0,
        "mantle_velocity": 0.0,
        "ero_stages": [],
    },
    "age_prediction": {
        "no_calc_ages": False,
        "ketch_aft": True,
        "madtrax_aft": False,
        "madtrax_aft_kinetic_model": 1,
        "madtrax_zft_kinetic_model": 1,
        "ap_rad": 45.0,
        "ap_uranium": 10.0,
        "ap_thorium": 40.0,
        "zr_rad": 60.0,
        "zr_uranium": 100.0,
        "zr_thorium": 40.0,
        "pad_time": 0.0,
        "past_age_increment": 0.0,
    },
    "observations": {
        "obs_age_file": "",
        "obs_ahe": [],
        "obs_ahe_stdev": [],
        "obs_aft": [],
        "obs_aft_stdev": [],
        "obs_zhe": [],
        "obs_zhe_stdev": [],
        "obs_zft": [],
        "obs_zft_stdev": [],
        "misfit_num_params": 0,
        "misfit_type": 1,
    },
    "plotting": {
        "no_plot_results": False,
        "no_display_plots": True,
        "plot_myr": False,
        "plot_depth_history": False,
        "plot_fault_depth_history": False,
        "invert_tt_plot": False,
        "t_plots": [0.1, 1, 5, 10, 20, 30, 50],
        "crust_solidus": False,
        "crust_solidus_comp": "wet_intermediate",
        "mantle_solidus": False,
        "mantle_solidus_xoh": 0.0,
        "solidus_ranges": False,
    },
    "output": {
        "log_output": False,
        "log_file": "",
        "model_id": "",
        "write_temps": False,
        "write_past_ages": False,
        "write_age_output": False,
        "save_plots": True,
    },
    "advanced": {
        "read_temps": False,
        "compare_temps": False,
    },
    "inversion": {
        "neighbourhood_algorithm": {
            "na_ns": 24,
            "na_nr": 12,
            "na_ni": 50,
            "na_n": 6,
            "na_n_resample": 2000,
            "na_n_walkers": 5,
        },
        "mcmc": {
            "mcmc_nwalkers": 8,
            "mcmc_nsteps": 50,
            "mcmc_discard": 5,
            "mcmc_thin": 3,
        },
    },
}


def default_config() -> dict[str, Any]:
    """Return a fresh copy of the GUI's default Tc1D YAML config."""
    return deepcopy(DEFAULT_CONFIG)


def merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge an imported YAML mapping into a default config."""
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a config with run-control flags aligned to Tc1D CLI validation."""
    normalized = merge_config(default_config(), config)
    general = normalized["general"]
    run_type = str(general.get("run_type", "forward")).strip().lower()
    # The GUI shows one run-type control and derives the legacy flags from it;
    # this avoids combinations like run_type=forward with inverse_mode=true.
    general["run_type"] = run_type
    general["batch_mode"] = run_type == "batch"
    general["inverse_mode"] = run_type in {"na", "mcmc"}

    erosion_model = normalized["erosion_model"]
    erosion_model["ero_type"] = int(erosion_model.get("ero_type", 1))
    return normalized


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate GUI-level config constraints before handing YAML to Tc1D."""
    errors: list[str] = []
    general = config.get("general", {})
    run_type = str(general.get("run_type", "")).strip().lower()

    if run_type not in RUN_TYPES:
        errors.append(f"Run type must be one of {', '.join(RUN_TYPES)}.")
    if run_type in {"na", "mcmc"} and not general.get("inverse_mode", False):
        errors.append(f"Run type '{run_type}' requires inverse_mode: true.")
    if run_type in {"forward", "batch"} and general.get("inverse_mode", False):
        errors.append(
            f"Run type '{run_type}' is not compatible with inverse_mode: true."
        )
    if general.get("batch_mode", False) and run_type != "batch":
        errors.append("batch_mode: true is only valid with run_type: batch.")

    erosion_model = config.get("erosion_model", {})
    try:
        ero_type = int(erosion_model.get("ero_type", 1))
    except (TypeError, ValueError):
        errors.append("Erosion type must be an integer from 0 to 7.")
        ero_type = -1

    if ero_type < 0 or ero_type > 7:
        errors.append("Erosion type must be an integer from 0 to 7.")
    if ero_type == 0:
        stages = erosion_model.get("ero_stages", [])
        if not isinstance(stages, list) or not stages:
            errors.append("Erosion type 0 requires at least one erosion stage.")
        else:
            # Type 0 is the GUI/YAML multi-stage path, so catch simple stage
            # mistakes before a model subprocess is launched.
            errors.extend(validate_erosion_stages(stages))

    for section, key in SCALAR_ONLY_FIELDS:
        container: Any = config
        for part in section.split("."):
            if not isinstance(container, dict):
                container = {}
                break
            container = container.get(part, {})
        if isinstance(container, dict) and isinstance(container.get(key), list):
            errors.append(
                f"{section}.{key} must be a single value, not a range/list."
            )

    return errors


def validate_erosion_stages(stages: list[dict[str, Any]]) -> list[str]:
    """Validate the GUI representation of type-0 erosion stages."""
    errors: list[str] = []
    for index, stage in enumerate(stages, start=1):
        stage_type = stage.get("type")
        unit = stage.get("unit")
        if stage_type not in EROSION_STAGE_TYPES:
            errors.append(
                f"Stage {index}: type must be constant, linear, or exponential."
            )
        if unit not in EROSION_STAGE_UNITS:
            errors.append(f"Stage {index}: unit must be erosion_rate or thickness.")
        if stage.get("duration_myr", "") in ("", None):
            errors.append(f"Stage {index}: duration_myr is required.")
        if stage.get("parameter1", "") in ("", None):
            errors.append(f"Stage {index}: parameter1 is required.")
        if stage_type in {"linear", "exponential"} and stage.get("parameter2", "") in (
            "",
            None,
        ):
            errors.append(f"Stage {index}: parameter2 is required for {stage_type}.")
        if stage_type == "exponential" and stage.get("parameter3", "") in ("", None):
            errors.append(
                f"Stage {index}: parameter3 is required for exponential stages."
            )
    return errors


def parse_yaml_text(text: str) -> dict[str, Any]:
    """Parse YAML text into a normalized config."""
    loaded = yaml.safe_load(text) if text.strip() else {}
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError("YAML input must be a mapping at the top level.")
    return normalize_config(merge_config(default_config(), loaded))


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """Read and normalize a Tc1D YAML config from disk."""
    return parse_yaml_text(Path(path).read_text(encoding="utf-8"))


def dump_yaml(config: dict[str, Any]) -> str:
    """Serialize a normalized config to YAML."""
    return yaml.safe_dump(normalize_config(config), sort_keys=False)


def write_yaml_file(config: dict[str, Any], path: str | Path) -> Path:
    """Write a normalized config to disk and return the path."""
    output_path = Path(path)
    output_path.write_text(dump_yaml(config), encoding="utf-8")
    return output_path


def parse_entry_value(text: str, cast: Callable[[str], Any] = float) -> Any:
    """Parse a GUI field as a scalar or a two-plus item YAML-style list."""
    stripped = text.strip()
    if not stripped:
        return ""
    # Ranges are entered as "min, max" in the GUI and serialized as YAML lists.
    # Scalars remain scalars, which is how Tc1D distinguishes fixed values from
    # inverse-search bounds.
    if stripped.startswith("[") and stripped.endswith("]"):
        parsed = yaml.safe_load(stripped)
        if isinstance(parsed, list):
            return [cast(str(item)) for item in parsed]
    if "," in stripped:
        return [cast(part.strip()) for part in stripped.split(",") if part.strip()]
    return cast(stripped)


def format_entry_value(value: Any) -> str:
    """Format a scalar or list value for a GUI entry field."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return "" if value is None else str(value)
