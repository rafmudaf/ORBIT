"""
Provides a library for sub configurations within ORBIT. By default, the library
is located at `../ORBIT/library/`, but it can also be stored outside of the
repo by passing in the `library_path` variable to `ProjectManager` or any
individual phases.

ORBIT expects a library outside of the repo to have the following structure:
```
<library folder name>
├── defaults         <- Top-level default data
├── project
│   ├── config       <- Configuration dictionary repository
│   ├── port         <- Port specific data setttings
│   ├── plant        <- Wind farm specific data setttings
│   ├── site         <- Project site data settings
│   ├── development  <- Project development cost settings
├── cables           <- Cable data files: array cables, export cables
├── substructures    <- Substructure data files: monopiles, jackets, etc.
├── turbines         <- Turbine data files
├── vessels          <- Vessel data files
│   ├── defaults     <- Default data related to vessel tasks
├── weather          <- Weather profiles
├── results
```
"""

__author__ = "Rob Hammond"
__copyright__ = "Copyright 2019, National Renewable Energy Laboratory"
__maintainer__ = "Rob Hammond"
__email__ = "robert.hammond@nrel.gov"


import os
import csv
import warnings

import yaml
import pandas as pd

from ORBIT.simulation.exceptions import LibraryItemNotFoundError

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


ROOT = os.path.abspath(os.path.join(os.path.abspath(__file__), "../.."))
default_library = os.path.join(ROOT, "library")


def clean_warning(message, category, filename, lineno, file=None, line=""):
    return f"{category.__name__}: {filename}:{lineno}\n{message}"


warnings.formatwarning = clean_warning


def initialize_library(library_path):
    """
    Creates an environment variable named "DATA_LIBRARY", defaulting to
    `../ORBIT/library/` if not defined.

    Parameters
    ----------
    library_path : str | None
        Absolute path to the project library.
    """

    library_exists = "DATA_LIBRARY" in os.environ
    if library_path is None:
        library_path = default_library

    if not os.path.isdir(library_path):
        raise ValueError(f"Invalid library path.")

    if library_exists and library_path != os.environ["DATA_LIBRARY"]:
        message = (
            f"Environment variable 'DATA_LIBRARY': "
            f"{os.environ['DATA_LIBRARY']} will be changed to: {library_path}."
        )
        warnings.warn(message)
    elif library_exists and library_path == os.environ["DATA_LIBRARY"]:
        return

    os.environ["DATA_LIBRARY"] = library_path
    print(f"ORBIT library intialized at '{library_path}'")


def extract_library_data(config, additional_keys=[]):
    """
    Extracts the configuration data from the specified library.

    Parameters
    ----------
    config : dict
        Configuration dictionary.
    additional_keys : list
        Additional keys that contain data that needs to be extracted from
        within `config`, by default [].

    Returns
    -------
    config : dict
        Configuration dictionary.
    """

    if os.environ.get("DATA_LIBRARY", None) is None:
        return config

    for key, val in config.items():
        if isinstance(val, dict) and any(el in key for el in additional_keys):
            config[key] = extract_library_data(val)
        elif not isinstance(val, str):
            continue

        try:
            config[key] = extract_library_specs(key, val)
        except KeyError:
            continue

    return config


def extract_library_specs(key, filename, file_type="yaml"):
    """
    Base method that extracts a file from the configured data library. If the
    file is not found in the configured library, the default library located
    within the repository will also be searched.

    Parameters
    ----------
    key : str
        Configuration key used to map to specific subpath in library.
    filename : str
        Name of the file to be extracted.
    file_type : str
        Should be one of "yaml" or "csv".

    Returns
    -------
    dict
        Dictionary of specifications for `filename`.

    Raises
    ------
    LibraryItemNotFoundError
        An error is raised when the file cannot be found in the library or the
        default library.
    """

    filename = f"{filename}.{file_type}"
    path = PATH_LIBRARY[key]
    filepath = os.path.join(os.environ["DATA_LIBRARY"], path, filename)

    if os.path.isfile(filepath):
        return _extract_file(filepath)

    if os.environ["DATA_LIBRARY"] != default_library:
        filepath = os.path.join(default_library, path, filename)
        if os.path.isfile(filepath):
            return _extract_file(filepath)

    raise LibraryItemNotFoundError(path, filename)


def _extract_file(filepath):
    """
    Extracts file from valid filepath. Currently only supports "yaml" or "csv".

    Parameters
    ----------
    filepath : str
        Valid filepath of library item.
    """

    if filepath.endswith("yaml"):
        return yaml.load(open(filepath, "r"), Loader=Loader)

    elif filepath.endswith("csv"):
        df = pd.read_csv(filepath, index_col=False)

        # Drop empty rows and columns
        df.dropna(how="all", inplace=True)
        df.dropna(how="all", inplace=True, axis=1)

        # Enforce strictly lowercase and "_" separated column names
        df.columns = [el.replace(" ", "_").lower() for el in df.columns]
        return df

    else:
        _type = filepath.split(".")[-1]
        raise TypeError(f"File type {_type} not supported for extraction.")


def _get_yes_no_response(filename):
    """Elicits a y/n response from the user to overwrite a file.

    Returns
    -------
    bool
        Indicator to overwrite `filename`.
    """

    response = input(f"{filename} already exists, overwrite [y/n]?").lower()
    if response not in ("y", "n"):
        print("Bad input! Must be one of [y/n]")
        _get_yes_no_response(filename)
    return True if response == "y" else False


def export_library_specs(key, filename, data, file_ext="yaml"):
    """
    Base method that export a file to the data library.

    Parameters
    ----------
    key : str
        Configuration key used to map to a specific subpath in library.
    filename : str
        Name to be given to the file without the extension.
    data : yaml-ready or List[list]
        Data to be saved to YAML (any Python type) or csv-ready.
    """

    filename = f"{filename}.{file_ext}"
    path = PATH_LIBRARY[key]
    data_path = os.path.join(os.environ["DATA_LIBRARY"], path, filename)
    if not _get_yes_no_response(data_path):
        print("Cancelling save!")
        return
    if file_ext == "yaml":
        yaml.dump(
            data, open(data_path, "w"), Dumper=Dumper, default_flow_style=False
        )
    elif file_ext == "csv":
        with open(data_path, "w") as f:
            writer = csv.writer(f)
            writer.writerows(data)
    print("Save complete!")


PATH_LIBRARY = {
    # vessels
    "array_cable_lay_vessel": "vessels",
    "export_cable_lay_vessel": "vessels",
    "oss_install_vessel": "vessels",
    "scour_protection_install_vessel": "vessels",
    "trench_dig_vessel": "vessels",
    "feeder": "vessels",
    "wtiv": "vessels",
    # cables
    "cables": "cables",
    "array_system": "cables",
    "array_system_design": "cables",
    "export_system": "cables",
    "export_system_design": "cables",
    # project details
    "config": os.path.join("project", "config"),
    "plant": os.path.join("project", "plant"),
    "port": os.path.join("project", "port"),
    "project_development": os.path.join("project", "development"),
    "site": os.path.join("project", "site"),
    # substructures
    "monopile": "substructures",
    "monopile_design": "substructures",
    "scour_protection": "substructures",
    "scour_design": "substructures",
    "transition_piece": "substructures",
    "offshore_substation_substructure": "substructures",
    "offshore_substation_topside": "substructures",
    # turbine
    "turbine": "turbines",
}
