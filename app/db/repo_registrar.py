# crud/registrar.py

class RepositoryRegistrar:
    registry: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        name = cls.__name__.replace("Repository", "").lower()
        RepositoryRegistrar.registry[name] = cls
