import typing as T


class Depends:
    def __init__(self, dependency: T.Callable):
        self.dependency = dependency


__all__ = ["Depends"]
