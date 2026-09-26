from pathlib import Path
import json
import pytest

from continuity.config import Settings
from continuity.storage import make_store
from continuity.retrieval import Retriever
from continuity.workflow import ReviewEngine
from continuity.schemas import PackageInput
from continuity.service import ingest_package

ROOT = Path(__file__).resolve().parents[1]


def fixture_package(version="v1", study="SYN-014"):
    data = json.loads((ROOT / "demo" / f"{version}.json").read_text())
    data["study_id"] = study
    return data


@pytest.fixture
def system(tmp_path):
    settings = Settings(data_dir=tmp_path)
    store = make_store(settings)
    retriever = Retriever(store, settings)
    engine = ReviewEngine(store, settings, retriever)
    yield settings, store, retriever, engine
    engine.close()
    store.close()


def ingest(system, version="v1", study="SYN-014"):
    return ingest_package(system[1], system[2], PackageInput.model_validate(fixture_package(version, study)))


def finish(engine, package, force_full=False):
    return engine.execute(engine.create(package, force_full)["id"])
