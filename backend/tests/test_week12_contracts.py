"""Week 12 regression coverage for source classification and uploaded evidence."""
from io import BytesIO

import pytest
from fastapi import HTTPException

from backend.app.db.database import IncidentDatabase
from backend.app.db.models import SafetyIncidentRecord
from backend.app.services import video_storage
from backend.pipeline.har import is_webcam_source


class FakeUpload:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.file = BytesIO(content)
        self.closed = False

    def close(self) -> None:
        self.file.close()
        self.closed = True


@pytest.mark.parametrize("source", [0, 1, 2, "0", "1", "webcam", ""])
def test_webcam_sources_are_classified_as_live(source):
    assert is_webcam_source(source)


@pytest.mark.parametrize("source", ["data/videos/clip.mp4", "rtsp://camera/stream", "source/site.mkv"])
def test_recorded_and_network_sources_are_not_classified_as_webcams(source):
    assert not is_webcam_source(source)


def test_incident_video_path_survives_database_round_trip(tmp_path):
    database = IncidentDatabase(tmp_path / "incidents.db", tmp_path / "snapshots")
    incident = SafetyIncidentRecord(
        track_id=7,
        event_type="FALL",
        video_path="/videos/uploaded_clip.mp4",
    )

    incident_id = database.insert_incident(incident)
    loaded = database.get_incident(incident_id)

    assert loaded is not None
    assert loaded.video_path == "/videos/uploaded_clip.mp4"


def test_video_upload_is_saved_and_listed(monkeypatch, tmp_path):
    monkeypatch.setattr(video_storage, "VIDEO_DIR", tmp_path / "videos")
    upload = FakeUpload(filename="site_clip.mp4", content=b"small video payload")

    result = video_storage.save_uploaded_video(upload)
    history = video_storage.list_uploaded_videos()

    assert result["name"] == "site_clip.mp4"
    assert (tmp_path / "videos" / result["source"].split("/")[-1]).read_bytes() == b"small video payload"
    assert history[0]["url"] == result["url"]
    assert history[0]["name"] == "site_clip.mp4"


def test_video_upload_rejects_non_video_extensions(monkeypatch, tmp_path):
    monkeypatch.setattr(video_storage, "VIDEO_DIR", tmp_path / "videos")
    upload = FakeUpload(filename="secrets.txt", content=b"not a video")

    with pytest.raises(HTTPException) as error:
        video_storage.save_uploaded_video(upload)

    assert error.value.status_code == 400
