"""Snapshot undo stack. States are immutable trees, so storing them is free."""
from __future__ import annotations


class History:
    def __init__(self, initial):
        self._undo = [initial]
        self._redo: list = []

    @property
    def current(self):
        return self._undo[-1]

    def push(self, state) -> None:
        self._undo.append(state)
        self._redo.clear()

    def undo(self):
        if len(self._undo) > 1:
            self._redo.append(self._undo.pop())
        return self.current

    def redo(self):
        if self._redo:
            self._undo.append(self._redo.pop())
        return self.current

    def can_undo(self) -> bool:
        return len(self._undo) > 1

    def can_redo(self) -> bool:
        return bool(self._redo)
