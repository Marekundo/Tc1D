"""Tkinter desktop application for configuring and running Tc1D.

The GUI is intentionally thin: it edits a YAML-compatible config, writes that
config into a per-run directory, and launches the existing Tc1D CLI in a
subprocess. Model calculations stay in the original scientific modules.
"""

from __future__ import annotations

from pathlib import Path
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable

from .config import (
    EROSION_STAGE_TYPES,
    EROSION_STAGE_UNITS,
    default_config,
    dump_yaml,
    format_entry_value,
    load_yaml_file,
    normalize_config,
    parse_entry_value,
    parse_yaml_text,
    validate_config,
    write_yaml_file,
)
from .runner import (
    PreparedRun,
    collect_result_files,
    missing_required_executables,
    prepare_run,
    start_process,
)


FieldSpec = tuple[str, str, str, Callable[[str], Any]]


FLOAT_FIELDS: tuple[FieldSpec, ...] = (
    ("geometry_time", "length", "Model depth extent (km)", float),
    ("geometry_time", "time", "Simulation time (Myr)", float),
    ("geometry_time", "dt", "Time step (years)", float),
    ("geometry_time", "init_moho_depth", "Initial Moho depth (km)", float),
    ("geometry_time", "removal_fraction", "Mantle removal fraction", float),
    ("geometry_time", "removal_start_time", "Removal start time (Myr)", float),
    ("geometry_time", "removal_end_time", "Removal end time (Myr)", float),
    ("thermal_model", "temp_surf", "Surface temperature (C)", float),
    ("thermal_model", "temp_base", "Basal temperature (C)", float),
    ("intrusion_model", "intrusion_temperature", "Intrusion temperature (C)", float),
    ("intrusion_model", "intrusion_start_time", "Intrusion start time (Myr)", float),
    ("intrusion_model", "intrusion_duration", "Intrusion duration (Myr)", float),
    ("intrusion_model", "intrusion_thickness", "Intrusion thickness (km)", float),
    ("intrusion_model", "intrusion_base_depth", "Intrusion base depth (km)", float),
    ("materials", "rho_crust", "Crust density (kg/m^3)", float),
    ("materials", "cp_crust", "Crust heat capacity (J/kg/K)", float),
    ("materials", "k_crust", "Crust conductivity (W/m/K)", float),
    ("materials", "heat_prod_crust", "Crust heat production (uW/m^3)", float),
    ("materials", "heat_prod_decay_depth", "Heat production decay depth (km)", float),
    ("materials", "alphav_crust", "Crust thermal expansion (1/K)", float),
    ("materials", "rho_mantle", "Mantle density (kg/m^3)", float),
    ("materials", "cp_mantle", "Mantle heat capacity (J/kg/K)", float),
    ("materials", "k_mantle", "Mantle conductivity (W/m/K)", float),
    ("materials", "heat_prod_mantle", "Mantle heat production (uW/m^3)", float),
    ("materials", "alphav_mantle", "Mantle thermal expansion (1/K)", float),
    ("materials", "rho_a", "Asthenosphere density (kg/m^3)", float),
    ("materials", "k_a", "Asthenosphere conductivity (W/m/K)", float),
    ("erosion_model", "vx_init", "Initial advection velocity (mm/yr)", float),
    ("erosion_model", "ero_option1", "Erosion option 1", float),
    ("erosion_model", "ero_option2", "Erosion option 2", float),
    ("erosion_model", "ero_option3", "Erosion option 3", float),
    ("erosion_model", "ero_option4", "Erosion option 4", float),
    ("erosion_model", "ero_option5", "Erosion option 5", float),
    ("erosion_model", "ero_option6", "Erosion option 6", float),
    ("erosion_model", "ero_option7", "Erosion option 7", float),
    ("erosion_model", "ero_option8", "Erosion option 8", float),
    ("erosion_model", "ero_option9", "Erosion option 9", float),
    ("erosion_model", "ero_option10", "Erosion option 10", float),
    ("erosion_model", "mantle_velocity", "Mantle velocity (mm/yr)", float),
    ("age_prediction", "ap_rad", "Apatite radius (um)", float),
    ("age_prediction", "ap_uranium", "Apatite U (ppm)", float),
    ("age_prediction", "ap_thorium", "Apatite Th (ppm)", float),
    ("age_prediction", "zr_rad", "Zircon radius (um)", float),
    ("age_prediction", "zr_uranium", "Zircon U (ppm)", float),
    ("age_prediction", "zr_thorium", "Zircon Th (ppm)", float),
    ("age_prediction", "pad_time", "Pad time (Myr)", float),
    ("age_prediction", "past_age_increment", "Past age increment (Myr)", float),
    ("plotting", "mantle_solidus_xoh", "Mantle solidus water (ppm)", float),
)

INT_FIELDS: tuple[FieldSpec, ...] = (
    ("geometry_time", "nx", "Grid points", int),
    ("age_prediction", "madtrax_aft_kinetic_model", "MadTrax AFT kinetic model", int),
    ("age_prediction", "madtrax_zft_kinetic_model", "MadTrax ZFT kinetic model", int),
    ("observations", "misfit_num_params", "Misfit parameter count", int),
    ("observations", "misfit_type", "Misfit type", int),
    ("inversion.neighbourhood_algorithm", "na_ns", "NA samples per iteration", int),
    ("inversion.neighbourhood_algorithm", "na_nr", "NA cells to resample", int),
    (
        "inversion.neighbourhood_algorithm",
        "na_ni",
        "NA initial random search size",
        int,
    ),
    ("inversion.neighbourhood_algorithm", "na_n", "NA iterations", int),
    ("inversion.neighbourhood_algorithm", "na_n_resample", "NA appraiser samples", int),
    ("inversion.neighbourhood_algorithm", "na_n_walkers", "NA appraiser walkers", int),
    ("inversion.mcmc", "mcmc_nwalkers", "MCMC walkers", int),
    ("inversion.mcmc", "mcmc_nsteps", "MCMC steps per walker", int),
    ("inversion.mcmc", "mcmc_discard", "MCMC burn-in discard", int),
    ("inversion.mcmc", "mcmc_thin", "MCMC thinning", int),
)

LIST_FIELDS: tuple[FieldSpec, ...] = (
    ("plotting", "t_plots", "Temperature plot times (Myr)", float),
    ("observations", "obs_ahe", "Observed AHe ages (Ma)", float),
    ("observations", "obs_ahe_stdev", "Observed AHe stdevs (Ma)", float),
    ("observations", "obs_aft", "Observed AFT ages (Ma)", float),
    ("observations", "obs_aft_stdev", "Observed AFT stdevs (Ma)", float),
    ("observations", "obs_zhe", "Observed ZHe ages (Ma)", float),
    ("observations", "obs_zhe_stdev", "Observed ZHe stdevs (Ma)", float),
    ("observations", "obs_zft", "Observed ZFT ages (Ma)", float),
    ("observations", "obs_zft_stdev", "Observed ZFT stdevs (Ma)", float),
)

BOOL_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("general", "batch_mode", "Batch mode"),
    ("general", "inverse_mode", "Inverse mode"),
    ("general", "debug", "Debug output"),
    ("general", "echo_inputs", "Echo inputs"),
    ("general", "no_echo_info", "Hide model info"),
    ("general", "no_echo_thermal_info", "Hide thermal info"),
    ("general", "no_echo_ages", "Hide age output"),
    ("geometry_time", "crustal_uplift", "Crustal uplift only"),
    ("geometry_time", "fixed_moho", "Fixed Moho"),
    ("thermal_model", "explicit", "Use explicit solver"),
    ("thermal_model", "mantle_adiabat", "Use mantle adiabat"),
    ("age_prediction", "no_calc_ages", "Disable age calculation"),
    ("age_prediction", "ketch_aft", "Use Ketcham AFT"),
    ("age_prediction", "madtrax_aft", "Use MadTrax AFT"),
    ("plotting", "no_plot_results", "Do not create plots"),
    ("plotting", "no_display_plots", "Do not display plots"),
    ("plotting", "plot_myr", "Plot model time in Myr"),
    ("plotting", "plot_depth_history", "Plot depth history"),
    ("plotting", "plot_fault_depth_history", "Plot fault depth history"),
    ("plotting", "invert_tt_plot", "Invert t-T plot"),
    ("plotting", "crust_solidus", "Plot crust solidus"),
    ("plotting", "mantle_solidus", "Plot mantle solidus"),
    ("plotting", "solidus_ranges", "Plot solidus ranges"),
    ("output", "log_output", "Write run log CSV"),
    ("output", "write_temps", "Write temperature CSV"),
    ("output", "write_past_ages", "Write past ages CSV"),
    ("output", "write_age_output", "Write age summary CSV"),
    ("output", "save_plots", "Save plots"),
    ("advanced", "read_temps", "Read temperatures from file"),
    ("advanced", "compare_temps", "Compare temperatures"),
)

STRING_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("observations", "obs_age_file", "Observed age CSV"),
    ("plotting", "crust_solidus_comp", "Crust solidus composition"),
    ("output", "log_file", "Log CSV filename"),
    ("output", "model_id", "Model ID"),
)


class Tc1DGuiApp:
    """Main Tkinter app for the Tc1D GUI."""

    def __init__(self, root: tk.Tk | None = None) -> None:
        self.root = root or tk.Tk()
        self.root.title("Tc1D Desktop GUI")
        self.root.geometry("1180x820")
        # The form is backed by the same nested mapping that is written to YAML.
        # Tk variables keep widgets simple, while form_config/load_config do the
        # conversion between text boxes and typed Tc1D values.
        self.config: dict[str, Any] = default_config()
        self.entry_vars: dict[tuple[str, str], tuple[tk.StringVar, Callable]] = {}
        self.bool_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self.string_vars: dict[tuple[str, str], tk.StringVar] = {}
        self.ero_stages: list[dict[str, Any]] = []
        self.output_root_var = tk.StringVar(value=str(Path.cwd() / "tc1d_gui_runs"))
        # Subprocess state is kept on the app so the Run/Cancel buttons, log
        # reader thread, and results refresh all refer to the same run.
        self.process: subprocess.Popen[str] | None = None
        self.prepared_run: PreparedRun | None = None
        self.output_queue: queue.Queue[str | None] = queue.Queue()
        self.preview_image: tk.PhotoImage | None = None

        self._build_styles()
        self._build_ui()
        self.load_config(self.config)

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.configure("TFrame", padding=4)
        style.configure("Section.TLabelframe", padding=8)
        style.configure("TButton", padding=(8, 4))

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self._build_run_tab()
        self._build_geometry_tab()
        self._build_materials_tab()
        self._build_erosion_tab()
        self._build_age_tab()
        self._build_plotting_tab()
        self._build_yaml_tab()
        self._build_results_tab()

        toolbar = ttk.Frame(self.root)
        toolbar.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        toolbar.columnconfigure(2, weight=1)
        self.run_button = ttk.Button(toolbar, text="Run", command=self.run_model)
        self.run_button.grid(row=0, column=0, padx=(0, 8))
        self.cancel_button = ttk.Button(
            toolbar,
            text="Cancel",
            command=self.cancel_run,
            state=tk.DISABLED,
        )
        self.cancel_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="Refresh YAML", command=self.refresh_yaml).grid(
            row=0, column=3, padx=(8, 0)
        )

    def _build_run_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Run")
        tab.columnconfigure(0, weight=1)

        run = ttk.LabelFrame(tab, text="Run control", style="Section.TLabelframe")
        run.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        run.columnconfigure(1, weight=1)
        ttk.Label(run, text="Run type").grid(row=0, column=0, sticky="w")
        self.run_type_var = tk.StringVar()
        run_type = ttk.Combobox(
            run,
            textvariable=self.run_type_var,
            values=("forward", "batch", "na", "mcmc"),
            state="readonly",
        )
        run_type.grid(row=0, column=1, sticky="ew", padx=8, pady=3)
        run_type.bind("<<ComboboxSelected>>", lambda _event: self._sync_run_flags())
        # batch_mode/inverse_mode are derived from run_type (see _sync_run_flags
        # and normalize_config), so they are shown read-only to reflect that.
        self._add_bool(
            run, "general", "batch_mode", "Batch mode (set by run type)", 1, 0,
            state=tk.DISABLED,
        )
        self._add_bool(
            run, "general", "inverse_mode", "Inverse mode (set by run type)", 1, 1,
            state=tk.DISABLED,
        )
        self._add_bool(run, "general", "debug", "Debug output", 2, 0)
        self._add_bool(run, "general", "echo_inputs", "Echo inputs", 2, 1)
        self._add_bool(run, "general", "no_echo_info", "Hide model info", 3, 0)
        self._add_bool(
            run,
            "general",
            "no_echo_thermal_info",
            "Hide thermal info",
            3,
            1,
        )
        self._add_bool(run, "general", "no_echo_ages", "Hide age output", 4, 0)

        paths = ttk.LabelFrame(tab, text="Run directory", style="Section.TLabelframe")
        paths.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        paths.columnconfigure(1, weight=1)
        ttk.Label(paths, text="Output root").grid(row=0, column=0, sticky="w")
        ttk.Entry(paths, textvariable=self.output_root_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=8,
            pady=3,
        )
        ttk.Button(paths, text="Browse", command=self.browse_output_root).grid(
            row=0,
            column=2,
            padx=(0, 8),
        )
        self._add_string(paths, "output", "model_id", "Model ID", 1, browse=False)
        self._add_string(paths, "output", "log_file", "Log CSV filename", 2)

        inversion = ttk.LabelFrame(
            tab,
            text="Inverse run controls",
            style="Section.TLabelframe",
        )
        inversion.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        inversion.columnconfigure(1, weight=1)
        for row, spec in enumerate(INT_FIELDS[5:]):
            self._add_entry(inversion, *spec, row=row)

    def _build_geometry_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Geometry/Thermal")
        tab.columnconfigure(0, weight=1)
        geometry = ttk.LabelFrame(tab, text="Geometry and time")
        geometry.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        geometry.columnconfigure(1, weight=1)
        for row, spec in enumerate(FLOAT_FIELDS[:6]):
            self._add_entry(geometry, *spec, row=row)
        self._add_entry(geometry, *INT_FIELDS[0], row=6)
        self._add_entry(geometry, *FLOAT_FIELDS[6], row=7)
        self._add_bool(
            geometry, "geometry_time", "crustal_uplift", "Crustal uplift", 8, 0
        )
        self._add_bool(geometry, "geometry_time", "fixed_moho", "Fixed Moho", 8, 1)

        thermal = ttk.LabelFrame(tab, text="Thermal model")
        thermal.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        thermal.columnconfigure(1, weight=1)
        self._add_bool(
            thermal, "thermal_model", "explicit", "Use explicit solver", 0, 0
        )
        self._add_bool(
            thermal,
            "thermal_model",
            "mantle_adiabat",
            "Use mantle adiabat",
            0,
            1,
        )
        for row, spec in enumerate(FLOAT_FIELDS[7:9], start=1):
            self._add_entry(thermal, *spec, row=row)

        intrusion = ttk.LabelFrame(tab, text="Magmatic intrusion")
        intrusion.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        intrusion.columnconfigure(1, weight=1)
        for row, spec in enumerate(FLOAT_FIELDS[9:14]):
            self._add_entry(intrusion, *spec, row=row)

    def _build_materials_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Materials")
        tab.columnconfigure(0, weight=1)
        materials = ttk.LabelFrame(tab, text="Material properties")
        materials.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        materials.columnconfigure(1, weight=1)
        materials.columnconfigure(3, weight=1)
        for index, spec in enumerate(FLOAT_FIELDS[14:27]):
            row = index % 7
            offset = 0 if index < 7 else 2
            self._add_entry(materials, *spec, row=row, column_offset=offset)

    def _build_erosion_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Erosion")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        erosion = ttk.LabelFrame(tab, text="Erosion model")
        erosion.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        erosion.columnconfigure(1, weight=1)
        ttk.Label(erosion, text="Erosion type").grid(row=0, column=0, sticky="w")
        self.ero_type_var = tk.StringVar()
        ttk.Combobox(
            erosion,
            textvariable=self.ero_type_var,
            values=[str(i) for i in range(8)],
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=3)

        erosion_fields = FLOAT_FIELDS[27:39]
        for index, spec in enumerate(erosion_fields, start=1):
            column_offset = 0 if index <= 6 else 2
            row = index if index <= 6 else index - 6
            self._add_entry(erosion, *spec, row=row, column_offset=column_offset)

        stages = ttk.LabelFrame(tab, text="Type 0 erosion stages")
        stages.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        stages.columnconfigure(0, weight=1)
        stages.rowconfigure(0, weight=1)
        columns = (
            "type",
            "unit",
            "duration_myr",
            "parameter1",
            "parameter2",
            "parameter3",
        )
        self.stage_tree = ttk.Treeview(
            stages, columns=columns, show="headings", height=7
        )
        for column in columns:
            self.stage_tree.heading(column, text=column)
            self.stage_tree.column(column, width=120, anchor="w")
        self.stage_tree.grid(row=0, column=0, columnspan=6, sticky="nsew")
        self.stage_tree.bind("<<TreeviewSelect>>", self._load_selected_stage)

        self.stage_type_var = tk.StringVar(value="constant")
        self.stage_unit_var = tk.StringVar(value="erosion_rate")
        self.stage_duration_var = tk.StringVar()
        self.stage_p1_var = tk.StringVar()
        self.stage_p2_var = tk.StringVar()
        self.stage_p3_var = tk.StringVar()
        editor = ttk.Frame(stages)
        editor.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        for col in range(6):
            editor.columnconfigure(col, weight=1)
        ttk.Combobox(
            editor,
            textvariable=self.stage_type_var,
            values=EROSION_STAGE_TYPES,
            state="readonly",
        ).grid(row=0, column=0, sticky="ew", padx=3)
        ttk.Combobox(
            editor,
            textvariable=self.stage_unit_var,
            values=EROSION_STAGE_UNITS,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Entry(editor, textvariable=self.stage_duration_var).grid(
            row=0,
            column=2,
            sticky="ew",
            padx=3,
        )
        ttk.Entry(editor, textvariable=self.stage_p1_var).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=3,
        )
        ttk.Entry(editor, textvariable=self.stage_p2_var).grid(
            row=0,
            column=4,
            sticky="ew",
            padx=3,
        )
        ttk.Entry(editor, textvariable=self.stage_p3_var).grid(
            row=0,
            column=5,
            sticky="ew",
            padx=3,
        )
        labels = ("type", "unit", "duration", "parameter1", "parameter2", "parameter3")
        for col, label in enumerate(labels):
            ttk.Label(editor, text=label).grid(row=1, column=col, sticky="w", padx=3)
        buttons = ttk.Frame(stages)
        buttons.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Add stage", command=self.add_stage).grid(
            row=0,
            column=0,
            padx=(0, 8),
        )
        ttk.Button(buttons, text="Update stage", command=self.update_stage).grid(
            row=0,
            column=1,
            padx=(0, 8),
        )
        ttk.Button(buttons, text="Remove stage", command=self.remove_stage).grid(
            row=0,
            column=2,
        )

    def _build_age_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Ages/Observations")
        tab.columnconfigure(0, weight=1)

        ages = ttk.LabelFrame(tab, text="Age prediction")
        ages.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ages.columnconfigure(1, weight=1)
        self._add_bool(ages, "age_prediction", "no_calc_ages", "Disable ages", 0, 0)
        self._add_bool(ages, "age_prediction", "ketch_aft", "Use Ketcham AFT", 0, 1)
        self._add_bool(ages, "age_prediction", "madtrax_aft", "Use MadTrax AFT", 1, 0)
        for row, spec in enumerate(INT_FIELDS[1:3], start=2):
            self._add_entry(ages, *spec, row=row)
        for row, spec in enumerate(FLOAT_FIELDS[39:47], start=4):
            self._add_entry(ages, *spec, row=row)

        obs = ttk.LabelFrame(tab, text="Observations")
        obs.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        obs.columnconfigure(1, weight=1)
        self._add_string(
            obs, "observations", "obs_age_file", "Observed age CSV", 0, browse=True
        )
        for row, spec in enumerate(LIST_FIELDS[1:], start=1):
            self._add_entry(obs, *spec, row=row, force_list=True)
        for row, spec in enumerate(INT_FIELDS[3:5], start=9):
            self._add_entry(obs, *spec, row=row)

    def _build_plotting_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Plotting/Output")
        tab.columnconfigure(0, weight=1)

        plotting = ttk.LabelFrame(tab, text="Plotting")
        plotting.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        plotting.columnconfigure(1, weight=1)
        plotting_bools = [
            ("no_plot_results", "Do not create plots"),
            ("no_display_plots", "Do not display plots"),
            ("plot_myr", "Plot model time in Myr"),
            ("plot_depth_history", "Plot depth history"),
            ("plot_fault_depth_history", "Plot fault depth history"),
            ("invert_tt_plot", "Invert t-T plot"),
            ("crust_solidus", "Plot crust solidus"),
            ("mantle_solidus", "Plot mantle solidus"),
            ("solidus_ranges", "Plot solidus ranges"),
        ]
        for index, (key, label) in enumerate(plotting_bools):
            self._add_bool(plotting, "plotting", key, label, index // 2, index % 2)
        self._add_entry(plotting, *LIST_FIELDS[0], row=5, force_list=True)
        self._add_string(
            plotting, "plotting", "crust_solidus_comp", "Crust composition", 6
        )
        self._add_entry(plotting, *FLOAT_FIELDS[-1], row=7)

        output = ttk.LabelFrame(tab, text="Output files")
        output.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        output_flags = [
            ("log_output", "Write run log CSV"),
            ("write_temps", "Write temperature CSV"),
            ("write_past_ages", "Write past ages CSV"),
            ("write_age_output", "Write age summary CSV"),
            ("save_plots", "Save plots"),
        ]
        for index, (key, label) in enumerate(output_flags):
            self._add_bool(output, "output", key, label, index // 2, index % 2)

        advanced = ttk.LabelFrame(tab, text="Advanced")
        advanced.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        self._add_bool(advanced, "advanced", "read_temps", "Read temperatures", 0, 0)
        self._add_bool(
            advanced, "advanced", "compare_temps", "Compare temperatures", 0, 1
        )

    def _build_yaml_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="YAML")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        self.yaml_text = ScrolledText(tab, height=28, wrap=tk.NONE)
        self.yaml_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        buttons = ttk.Frame(tab)
        buttons.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(buttons, text="Apply YAML", command=self.apply_yaml).grid(
            row=0,
            column=0,
            padx=(0, 8),
        )
        ttk.Button(buttons, text="Import YAML", command=self.import_yaml).grid(
            row=0,
            column=1,
            padx=(0, 8),
        )
        ttk.Button(buttons, text="Export YAML", command=self.export_yaml).grid(
            row=0,
            column=2,
        )

    def _build_results_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Run Log/Results")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        pane = ttk.PanedWindow(tab, orient=tk.VERTICAL)
        pane.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        log_frame = ttk.LabelFrame(pane, text="Run log")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = ScrolledText(log_frame, height=13, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        pane.add(log_frame, weight=1)

        result_frame = ttk.LabelFrame(pane, text="Generated files")
        result_frame.columnconfigure(1, weight=1)
        result_frame.rowconfigure(0, weight=1)
        self.result_list = tk.Listbox(result_frame, height=8)
        self.result_list.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self.result_list.bind("<<ListboxSelect>>", self.preview_selected_result)
        self.preview_frame = ttk.Frame(result_frame)
        self.preview_frame.grid(row=0, column=1, sticky="nsew")
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(0, weight=1)
        self.preview_text = ScrolledText(self.preview_frame, wrap=tk.NONE)
        self.preview_label = ttk.Label(self.preview_frame, anchor="center")
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        pane.add(result_frame, weight=1)

    def _add_entry(
        self,
        parent: tk.Widget,
        section: str,
        key: str,
        label: str,
        cast: Callable[[str], Any],
        row: int,
        column_offset: int = 0,
        force_list: bool = False,
    ) -> None:
        var = tk.StringVar()
        ttk.Label(parent, text=label).grid(
            row=row,
            column=column_offset,
            sticky="w",
            padx=(0, 8),
            pady=3,
        )
        ttk.Entry(parent, textvariable=var).grid(
            row=row,
            column=column_offset + 1,
            sticky="ew",
            padx=(0, 8),
            pady=3,
        )
        parser = (
            _parse_list_value(cast)
            if force_list
            else lambda text: parse_entry_value(text, cast)
        )
        self.entry_vars[(section, key)] = (var, parser)

    def _add_bool(
        self,
        parent: tk.Widget,
        section: str,
        key: str,
        label: str,
        row: int,
        column: int,
        state: str = tk.NORMAL,
    ) -> None:
        var = tk.BooleanVar()
        ttk.Checkbutton(parent, text=label, variable=var, state=state).grid(
            row=row,
            column=column,
            sticky="w",
            padx=(0, 16),
            pady=3,
        )
        self.bool_vars[(section, key)] = var

    def _add_string(
        self,
        parent: tk.Widget,
        section: str,
        key: str,
        label: str,
        row: int,
        browse: bool = False,
    ) -> None:
        var = tk.StringVar()
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=var).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=8,
            pady=3,
        )
        if browse:
            ttk.Button(
                parent,
                text="Browse",
                command=lambda: self.browse_file(var),
            ).grid(row=row, column=2, padx=(0, 8))
        self.string_vars[(section, key)] = var

    def load_config(self, config: dict[str, Any]) -> None:
        """Populate every widget from an imported or default config."""
        self.config = normalize_config(config)
        self.run_type_var.set(self.config["general"]["run_type"])
        self.ero_type_var.set(str(self.config["erosion_model"]["ero_type"]))

        for (section, key), (var, _parser) in self.entry_vars.items():
            var.set(format_entry_value(_nested_get(self.config, section, key)))
        for (section, key), var in self.bool_vars.items():
            var.set(bool(_nested_get(self.config, section, key)))
        for (section, key), var in self.string_vars.items():
            var.set(str(_nested_get(self.config, section, key) or ""))

        self.ero_stages = list(self.config["erosion_model"].get("ero_stages", []))
        self.refresh_stage_tree()
        self.refresh_yaml()

    def form_config(self) -> dict[str, Any]:
        """Collect widget values and return the normalized Tc1D config mapping."""
        config = default_config()
        config["general"]["run_type"] = self.run_type_var.get()
        config["erosion_model"]["ero_type"] = int(self.ero_type_var.get() or 1)

        # Entry parsers handle both scalar values and two-value ranges, because
        # the inverse run types use YAML lists for sampled parameter bounds.
        for (section, key), (var, parser) in self.entry_vars.items():
            text = var.get().strip()
            try:
                value = parser(text)
            except ValueError as exc:
                raise ValueError(f"{section}.{key}: {exc}") from exc
            _nested_set(config, section, key, value)
        for (section, key), var in self.bool_vars.items():
            _nested_set(config, section, key, bool(var.get()))
        for (section, key), var in self.string_vars.items():
            _nested_set(config, section, key, var.get().strip())

        config["erosion_model"]["ero_stages"] = list(self.ero_stages)
        return normalize_config(config)

    def refresh_yaml(self) -> None:
        """Regenerate the YAML preview from the current form state."""
        try:
            self.config = self.form_config()
            text = dump_yaml(self.config)
        except ValueError as exc:
            messagebox.showerror("Invalid form value", str(exc), parent=self.root)
            return
        self.yaml_text.delete("1.0", tk.END)
        self.yaml_text.insert("1.0", text)

    def apply_yaml(self) -> None:
        """Load the YAML preview back into the form."""
        try:
            config = parse_yaml_text(self.yaml_text.get("1.0", tk.END))
        except Exception as exc:
            messagebox.showerror("Invalid YAML", str(exc), parent=self.root)
            return
        self.load_config(config)

    def import_yaml(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Import Tc1D YAML",
            filetypes=(("YAML files", "*.yaml *.yml"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            self.load_config(load_yaml_file(path))
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self.root)

    def export_yaml(self) -> None:
        self.refresh_yaml()
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export Tc1D YAML",
            defaultextension=".yaml",
            filetypes=(("YAML files", "*.yaml *.yml"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            write_yaml_file(self.config, path)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)

    def browse_output_root(self) -> None:
        path = filedialog.askdirectory(parent=self.root, title="Choose output root")
        if path:
            self.output_root_var.set(path)

    def browse_file(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(parent=self.root, title="Choose file")
        if path:
            var.set(str(Path(path).resolve()))

    def _sync_run_flags(self) -> None:
        """Keep GUI flags aligned with the selected run type."""
        run_type = self.run_type_var.get()
        self.bool_vars[("general", "batch_mode")].set(run_type == "batch")
        self.bool_vars[("general", "inverse_mode")].set(run_type in {"na", "mcmc"})
        self.refresh_yaml()

    def add_stage(self) -> None:
        try:
            self.ero_stages.append(self._stage_from_editor())
        except ValueError as exc:
            messagebox.showerror("Invalid stage", str(exc), parent=self.root)
            return
        self.refresh_stage_tree()
        self.refresh_yaml()

    def update_stage(self) -> None:
        selected = self.stage_tree.selection()
        if not selected:
            return
        index = self.stage_tree.index(selected[0])
        try:
            self.ero_stages[index] = self._stage_from_editor()
        except ValueError as exc:
            messagebox.showerror("Invalid stage", str(exc), parent=self.root)
            return
        self.refresh_stage_tree()
        self.refresh_yaml()

    def remove_stage(self) -> None:
        selected = self.stage_tree.selection()
        if not selected:
            return
        index = self.stage_tree.index(selected[0])
        del self.ero_stages[index]
        self.refresh_stage_tree()
        self.refresh_yaml()

    def refresh_stage_tree(self) -> None:
        """Redraw the editable erosion-stage table."""
        self.stage_tree.delete(*self.stage_tree.get_children())
        for stage in self.ero_stages:
            values = (
                stage.get("type", ""),
                stage.get("unit", ""),
                format_entry_value(stage.get("duration_myr", "")),
                format_entry_value(stage.get("parameter1", "")),
                format_entry_value(stage.get("parameter2", "")),
                format_entry_value(stage.get("parameter3", "")),
            )
            self.stage_tree.insert("", tk.END, values=values)

    def _load_selected_stage(self, _event: tk.Event) -> None:
        selected = self.stage_tree.selection()
        if not selected:
            return
        stage = self.ero_stages[self.stage_tree.index(selected[0])]
        self.stage_type_var.set(str(stage.get("type", "constant")))
        self.stage_unit_var.set(str(stage.get("unit", "erosion_rate")))
        self.stage_duration_var.set(format_entry_value(stage.get("duration_myr", "")))
        self.stage_p1_var.set(format_entry_value(stage.get("parameter1", "")))
        self.stage_p2_var.set(format_entry_value(stage.get("parameter2", "")))
        self.stage_p3_var.set(format_entry_value(stage.get("parameter3", "")))

    def _stage_from_editor(self) -> dict[str, Any]:
        """Read the erosion-stage editor into the YAML stage schema."""
        stage = {
            "type": self.stage_type_var.get(),
            "unit": self.stage_unit_var.get(),
            "duration_myr": parse_entry_value(self.stage_duration_var.get(), float),
            "parameter1": parse_entry_value(self.stage_p1_var.get(), float),
        }
        if self.stage_p2_var.get().strip():
            stage["parameter2"] = parse_entry_value(self.stage_p2_var.get(), float)
        if self.stage_p3_var.get().strip():
            stage["parameter3"] = parse_entry_value(self.stage_p3_var.get(), float)
        return stage

    def run_model(self) -> None:
        """Validate the form, prepare a run directory, and start Tc1D."""
        try:
            config = self.form_config()
        except ValueError as exc:
            messagebox.showerror("Invalid form value", str(exc), parent=self.root)
            return

        errors = validate_config(config)
        if errors:
            messagebox.showerror(
                "Invalid configuration", "\n".join(errors), parent=self.root
            )
            return

        missing = []
        if not config.get("age_prediction", {}).get("no_calc_ages", False):
            missing = missing_required_executables()
        if missing:
            messagebox.showerror(
                "Tc_core executables missing",
                "The following required executables were not found on PATH:\n"
                + "\n".join(f"- {name}" for name in missing)
                + "\n\nInstall/build Tc_core before running Tc1D from the GUI.",
                parent=self.root,
            )
            return

        try:
            # Tc1D writes csv/ and png/ relative to the current working
            # directory, so each GUI launch gets its own timestamped folder.
            run_name = str(config.get("output", {}).get("model_id", ""))
            self.prepared_run = prepare_run(
                config,
                self.output_root_var.get(),
                run_name=run_name,
            )
        except Exception as exc:
            messagebox.showerror("Run setup failed", str(exc), parent=self.root)
            return

        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, f"Run directory: {self.prepared_run.run_dir}\n")
        self.log_text.insert(
            tk.END, f"Command: {' '.join(self.prepared_run.command)}\n\n"
        )
        self.result_list.delete(0, tk.END)
        self._set_running(True)

        try:
            self.process = start_process(self.prepared_run)
        except Exception as exc:
            self._set_running(False)
            messagebox.showerror("Run failed", str(exc), parent=self.root)
            return

        # Tkinter must be updated on the main thread. The reader thread only
        # pushes process output into a queue, and _drain_output_queue displays it.
        thread = threading.Thread(target=self._read_process_output, daemon=True)
        thread.start()
        self.root.after(100, self._drain_output_queue)

    def cancel_run(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._append_log("\nCancel requested.\n")

    def _read_process_output(self) -> None:
        """Read subprocess output without blocking the Tk event loop."""
        assert self.process is not None
        if self.process.stdout is not None:
            for line in self.process.stdout:
                self.output_queue.put(line)
        self.process.wait()
        self.output_queue.put(None)

    def _drain_output_queue(self) -> None:
        """Move queued subprocess output into the log widget."""
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                returncode = self.process.returncode if self.process else None
                self._append_log(f"\nRun finished with exit code {returncode}.\n")
                self._set_running(False)
                if self.prepared_run:
                    self.refresh_results(self.prepared_run.run_dir)
                return
            self._append_log(item)
        if self.process and self.process.poll() is None:
            self.root.after(100, self._drain_output_queue)

    def _append_log(self, text: str) -> None:
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _set_running(self, running: bool) -> None:
        self.run_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.cancel_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def refresh_results(self, run_dir: Path) -> None:
        """List generated CSV and PNG files after a run finishes."""
        self.result_list.delete(0, tk.END)
        self.result_paths = collect_result_files(run_dir)
        for path in self.result_paths:
            self.result_list.insert(tk.END, str(path.relative_to(run_dir)))
        if not self.result_paths:
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert(tk.END, "No generated CSV or PNG files found.")

    def preview_selected_result(self, _event: tk.Event) -> None:
        selected = self.result_list.curselection()
        if not selected:
            return
        path = self.result_paths[selected[0]]
        self.preview_text.grid_remove()
        self.preview_label.grid_remove()

        if path.suffix.lower() == ".png":
            try:
                image = tk.PhotoImage(file=str(path))
                factor = max(1, image.width() // 780, image.height() // 430)
                self.preview_image = image.subsample(factor, factor)
                self.preview_label.configure(image=self.preview_image, text="")
                self.preview_label.grid(row=0, column=0, sticky="nsew")
            except tk.TclError:
                self.preview_text.delete("1.0", tk.END)
                self.preview_text.insert(tk.END, f"Could not preview image: {path}")
                self.preview_text.grid(row=0, column=0, sticky="nsew")
            return

        self.preview_text.delete("1.0", tk.END)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(errors="replace").splitlines()
        self.preview_text.insert(tk.END, "\n".join(lines[:200]))
        if len(lines) > 200:
            self.preview_text.insert(tk.END, "\n... preview truncated ...")
        self.preview_text.grid(row=0, column=0, sticky="nsew")


def create_app(root: tk.Tk | None = None) -> Tc1DGuiApp:
    """Create the Tk app without entering the main loop."""
    return Tc1DGuiApp(root=root)


def main() -> None:
    """Launch the Tc1D desktop GUI."""
    app = create_app()
    app.root.mainloop()


def _nested_get(config: dict[str, Any], section: str, key: str) -> Any:
    current: Any = config
    for part in section.split("."):
        current = current[part]
    return current.get(key, "")


def _nested_set(config: dict[str, Any], section: str, key: str, value: Any) -> None:
    current: Any = config
    for part in section.split("."):
        current = current[part]
    current[key] = value


def _parse_list_value(cast: Callable[[str], Any]) -> Callable[[str], list[Any]]:
    def parser(text: str) -> list[Any]:
        parsed = parse_entry_value(text, cast)
        if parsed == "":
            return []
        if isinstance(parsed, list):
            return parsed
        return [parsed]

    return parser


if __name__ == "__main__":
    main()
