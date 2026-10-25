"""Immutable request scope, inspired by DeepTutor's workspace context boundary.

An explicit object fits this small synchronous service; no global current-notebook
variable or browser-selected scope is consulted during tool execution.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class NotebookContext:
    student_id: str
    notebook_id: str
    course_id: str
    revision: int
    sources: tuple[tuple[str, str, str], ...]

    def refs(self):
        return [dict(zip(('source_type', 'source_id', 'source_version'), item)) for item in self.sources]
