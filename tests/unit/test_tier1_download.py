from pathlib import Path

import pytest

from classifier.tier1 import download as download_module
from classifier.tier1.download import fetch_model_artifacts


class FakePaginator:
    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages

    def paginate(self, Bucket, Prefix):  # noqa: N803 - matches boto3's kwarg casing
        self.last_bucket = Bucket
        self.last_prefix = Prefix
        return self._pages


class FakeS3Client:
    def __init__(self, pages: list[dict]) -> None:
        self._paginator = FakePaginator(pages)
        self.downloaded: list[tuple[str, str, str]] = []

    def get_paginator(self, _name):
        return self._paginator

    def download_file(self, bucket, key, local_path):
        self.downloaded.append((bucket, key, local_path))
        Path(local_path).write_text("fake content")


def _patch_client(monkeypatch, fake_client: FakeS3Client):
    monkeypatch.setattr(download_module.boto3, "client", lambda *a, **kw: fake_client)


def test_downloads_every_object_under_the_version_prefix(monkeypatch, tmp_path):
    fake_client = FakeS3Client(
        pages=[
            {
                "Contents": [
                    {"Key": "v1-abc/model.onnx"},
                    {"Key": "v1-abc/tokenizer/vocab.json"},
                    {"Key": "v1-abc/calibration.json"},
                ]
            }
        ]
    )
    _patch_client(monkeypatch, fake_client)

    version_dir = fetch_model_artifacts("v1-abc", tmp_path, secret_access_key="secret")

    assert version_dir == tmp_path / "v1-abc"
    assert (version_dir / "model.onnx").exists()
    assert (version_dir / "tokenizer" / "vocab.json").exists()
    assert (version_dir / "calibration.json").exists()
    assert len(fake_client.downloaded) == 3


def test_skips_files_already_present(monkeypatch, tmp_path):
    fake_client = FakeS3Client(pages=[{"Contents": [{"Key": "v1-abc/model.onnx"}]}])
    _patch_client(monkeypatch, fake_client)

    version_dir = tmp_path / "v1-abc"
    version_dir.mkdir(parents=True)
    (version_dir / "model.onnx").write_text("already here")

    fetch_model_artifacts("v1-abc", tmp_path, secret_access_key="secret")

    assert fake_client.downloaded == []
    assert (version_dir / "model.onnx").read_text() == "already here"


def test_empty_prefix_exits(monkeypatch, tmp_path):
    fake_client = FakeS3Client(pages=[{"Contents": []}])
    _patch_client(monkeypatch, fake_client)

    with pytest.raises(SystemExit):
        fetch_model_artifacts("v1-missing", tmp_path, secret_access_key="secret")
