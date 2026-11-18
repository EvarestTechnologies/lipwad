from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def built_frontend(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>Lipwad</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')")
    return tmp_path


def test_api_still_answers_when_serving_the_frontend(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert client.get("/api/health").json() == {"status": "ok"}


def test_root_serves_the_built_frontend(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert "Lipwad" in client.get("/").text


def test_assets_are_served(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert client.get("/assets/app.js").status_code == 200


def test_client_side_routes_fall_back_to_the_app_shell(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert "Lipwad" in client.get("/claims/C01").text


def test_unknown_api_route_is_not_swallowed_by_the_app_shell(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert client.get("/api/missing").status_code == 404


def test_api_only_without_a_built_frontend() -> None:
    assert TestClient(create_app(None)).get("/").status_code == 404


def test_the_shell_and_worker_files_are_always_revalidated(tmp_path: Path) -> None:
    folder = built_frontend(tmp_path)
    for name in ("sw.js", "registerSW.js", "manifest.webmanifest"):
        (folder / name).write_text("// built")
    client = TestClient(create_app(folder))

    for path in (
        "/",
        "/claims/C01",
        "/index.html",
        "/sw.js",
        "/registerSW.js",
        "/manifest.webmanifest",
    ):
        assert client.get(path).headers["cache-control"] == "no-cache", path


def test_hashed_assets_are_cached_for_a_year(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert client.get("/assets/app.js").headers["cache-control"] == (
        "public, max-age=31536000, immutable"
    )


def test_api_responses_get_no_asset_caching(tmp_path: Path) -> None:
    client = TestClient(create_app(built_frontend(tmp_path)))

    assert "immutable" not in client.get("/api/health").headers.get("cache-control", "")
