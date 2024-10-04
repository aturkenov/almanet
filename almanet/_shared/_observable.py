__all__ = ["observable"]


class observable:

    def __init__(self):
        self.observers = []

    def add_observer(self, function):
        self.observers.append(function)

    def observer(self, function):
        self.add_observer(function)
        return function

    def notify(self, *args, **kwargs):
        for observer in self.observers:
            observer(*args, **kwargs)
