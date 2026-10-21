import json
from pathlib import Path

import pytest

from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def data_dir():
    return Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def raw_data(data_dir):
    return (json.loads((data_dir / "knowledge_points.json").read_text(encoding="utf-8")),
            json.loads((data_dir / "questions.json").read_text(encoding="utf-8")))


@pytest.fixture
def catalog(data_dir):
    return Catalog.load(data_dir)


@pytest.fixture
def service(catalog, tmp_path):
    with SQLiteRepository(tmp_path / "learning.sqlite3") as repository:
        result = LearningService(catalog, repository)
        result.register("student-a", ("logistic_regression",))
        yield result
