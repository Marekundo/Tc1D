import importlib.metadata


# Versioning
try:
    __version__ = importlib.metadata.version("tc1d")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0+unknown"


def init_params(*args, **kwargs):
    """Lazily import and call the scientific Tc1D parameter initializer."""
    from .tc1d import init_params as _init_params

    return _init_params(*args, **kwargs)


def prep_model(*args, **kwargs):
    """Lazily import and call the scientific Tc1D model runner."""
    from .tc1d import prep_model as _prep_model

    return _prep_model(*args, **kwargs)


__all__ = ["__version__", "init_params", "prep_model"]
