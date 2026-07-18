"""Feature validators package."""

from .profiler import ProfilerValidator

# Registry of all available feature validators
# Add new features here as they are implemented
FEATURE_REGISTRY = {
    "profiler": ProfilerValidator,
}

def get_validator(name: str):
    """Get a validator instance by name."""
    cls = FEATURE_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Unknown feature: {name}. Available: {list(FEATURE_REGISTRY.keys())}")
    return cls()

def list_features() -> list:
    """List all registered features."""
    return list(FEATURE_REGISTRY.keys())
