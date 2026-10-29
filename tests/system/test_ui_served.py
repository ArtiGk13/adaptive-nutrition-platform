"""The client is mounted at the root, which is the one place it could shadow the API.

These tests fix that boundary: the page and its two assets are served, and every router
registered before the mount still answers.
"""

USER_PAYLOAD = {
    "name": "UI User",
    "age": 30,
    "sex": "female",
    "height_cm": 168.0,
    "weight_kg": 72.0,
    "activity_level": "light",
    "goal_type": "weight_loss",
}


def test_root_serves_the_client(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Adaptive Nutrition" in response.text


def test_stylesheet_and_script_are_served(client):
    for path, fragment in (("/style.css", "--surface"), ("/app.js", "async function api")):
        response = client.get(path)
        assert response.status_code == 200, path
        assert fragment in response.text, path


def test_the_stylesheet_defines_a_dark_mode(client):
    """Both scopes are needed: the OS setting and an explicit theme stamp."""
    css = client.get("/style.css").text
    assert "prefers-color-scheme: dark" in css
    assert '[data-theme="dark"]' in css


def test_the_theme_can_be_chosen_and_is_applied_before_paint(client):
    page = client.get("/").text
    assert 'id="theme-toggle"' in page
    # the stored choice is read in the head, or the page flashes the other theme first
    head = page.split("</head>")[0]
    assert "localStorage" in head and "data-theme" in head


def test_the_cycle_figure_is_described_for_readers_who_cannot_see_it(client):
    page = client.get("/")
    assert 'role="img"' in page.text
    assert 'aria-label="The adaptation cycle' in page.text
    assert "<figcaption>" in page.text
    # drawn, not fetched: an external image would not survive an offline demonstration
    assert "<svg" in page.text and "<img" not in page.text


def test_narrow_screens_keep_the_theme_control(client):
    """The first version hid the whole sidebar footer below 880px, and the control
    with it, which left a phone no way to change theme."""
    css = client.get("/style.css").text
    narrow = css.split("@media (max-width: 880px)")[1]
    assert ".side-foot { display: none; }" not in narrow
    assert ".theme-toggle" in narrow


def test_the_mount_does_not_shadow_the_api(client):
    assert client.get("/health").json() == {"status": "ok"}

    created = client.post("/users", json=USER_PAYLOAD)
    assert created.status_code == 201
    user_id = created.json()["user_id"]

    assert client.get("/users").status_code == 200
    assert client.post(f"/users/{user_id}/plan").status_code == 201
    assert client.get(f"/users/{user_id}/plan").status_code == 200


def test_unknown_path_is_not_answered_with_the_page(client):
    """A missing endpoint must still be a 404, or a typo in a URL would look like success."""
    assert client.get("/users/9999/plan").status_code == 404
    assert client.get("/no-such-file.css").status_code == 404
