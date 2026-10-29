"""Collection services; lazy exports avoid repository/reader import cycles."""
__all__ = ["CollectionRunner", "CollectionRunResult"]


def __getattr__(name):
    if name in __all__:
        from collector.collection import runner
        return getattr(runner, name)
    raise AttributeError(name)
