"""Partner logos and the public partners list (home page strip)."""

from io import BytesIO

from PIL import Image


def _png(size=(300, 120), alpha=True) -> bytes:
    image = Image.new("RGBA" if alpha else "RGB", size, (0, 0, 0, 0) if alpha else (255, 255, 255))
    for x in range(min(40, size[0] - 1), min(120, size[0])):
        for y in range(min(30, size[1] - 1), min(90, size[1])):
            image.putpixel((x, y), (200, 30, 30, 255) if alpha else (200, 30, 30))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _partner(api, headers, **extra):
    body = {"name": "Amaia Land", "partner_type": "developer", "contact_person": "J. Cruz",
            "email": "sales@amaia.example", "phone_number": "0917 000 0000", "website": "amaia.example",
            "notes": "internal note", **extra}
    response = api.post("/api/v1/partners", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_logo_upload_keeps_shape_and_transparency(api, admin, employee):
    partner = _partner(api, admin)
    files = {"file": ("logo.png", _png((1200, 300)), "image/png")}
    assert api.put(f"/api/v1/partners/{partner['id']}/logo", headers=employee, files=files).status_code == 403
    saved = api.put(f"/api/v1/partners/{partner['id']}/logo", headers=admin, files=files)
    assert saved.status_code == 200 and saved.json()["logo_version"]
    logo = Image.open(BytesIO(api.get(f"/api/v1/partners/{partner['id']}/logo", headers=employee).content))
    assert logo.format == "PNG" and logo.mode == "RGBA"
    assert logo.size == (480, 120)  # fitted into 480x200, 4:1 kept
    assert logo.getpixel((0, 0))[3] == 0  # still transparent


def test_bad_logo_files_are_refused(api, admin):
    partner = _partner(api, admin)
    url = f"/api/v1/partners/{partner['id']}/logo"
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert api.put(url, headers=admin, files={"file": ("logo.svg", svg, "image/svg+xml")}).status_code == 422
    assert api.put(url, headers=admin, files={"file": ("tiny.png", _png((20, 10)), "image/png")}).status_code == 422
    assert api.put(url, headers=admin, files={"file": ("big.png", b"0" * (5 * 1024 * 1024 + 10), "image/png")}).status_code == 413


def test_public_list_shows_only_active_partners_and_safe_fields(api, admin):
    shown = _partner(api, admin)
    hidden = _partner(api, admin, name="Old Partner")
    api.put(f"/api/v1/partners/{hidden['id']}", headers=admin, json={"status": "inactive"})
    api.put(f"/api/v1/partners/{shown['id']}/logo", headers=admin, files={"file": ("l.png", _png(), "image/png")})
    api.put(f"/api/v1/partners/{hidden['id']}/logo", headers=admin, files={"file": ("l.png", _png(), "image/png")})

    public = api.get("/api/v1/public/partners").json()
    assert [p["name"] for p in public] == ["Amaia Land"]
    assert set(public[0]) == {"id", "name", "partner_type", "website", "logo_url"}
    assert public[0]["website"] == "https://amaia.example"
    assert "internal note" not in str(public) and "sales@amaia.example" not in str(public)
    assert api.get("/api/v1/public/home").json()["partners"] == public

    logo = api.get(public[0]["logo_url"])
    assert logo.status_code == 200 and logo.headers["content-type"] == "image/png"
    assert logo.headers["x-content-type-options"] == "nosniff"
    assert api.get(f"/api/v1/public/partners/{hidden['id']}/logo").status_code == 404


def test_removing_a_logo(api, admin):
    partner = _partner(api, admin)
    api.put(f"/api/v1/partners/{partner['id']}/logo", headers=admin, files={"file": ("l.png", _png(), "image/png")})
    cleared = api.delete(f"/api/v1/partners/{partner['id']}/logo", headers=admin)
    assert cleared.status_code == 200 and cleared.json()["logo_version"] is None
    assert api.get("/api/v1/public/partners").json()[0]["logo_url"] is None
    assert api.get(f"/api/v1/public/partners/{partner['id']}/logo").status_code == 404
