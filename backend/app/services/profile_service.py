"""v2 — Profile service + avatar upload.

Avatars are stored on the server-generated path layout:
  {avatar_local_root}/users/{user_id}/avatar-small.{ext}
  {avatar_local_root}/users/{user_id}/avatar-large.{ext}
The original upload is NEVER served to clients — only the cropped, re-encoded
small + large variants. Content type is validated by sniffing the first few
bytes (PNG, JPEG, WebP, GIF).
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps  # type: ignore

from ..core.errors import validation
from ..models.user import User
from ..schemas.auth import UserPublic

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG_SOI = b"\xff\xd8\xff"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"
_RIFF = b"RIFF"
_WEBP = b"WEBP"


def detect_image_format(head: bytes) -> str | None:
    """Return a normalised extension for the file's actual content, or None."""
    if head.startswith(_PNG):
        return "png"
    if head.startswith(_JPEG_SOI):
        return "jpg"
    if head[:6] in (_GIF87, _GIF89):
        return "gif"
    if head[:4] == _RIFF and head[8:12] == _WEBP:
        return "webp"
    return None


def _storage_root() -> Path:
    from ..core.config import get_settings
    return Path(get_settings().avatar_local_root)


def _user_dir(user_id: str) -> Path:
    d = _storage_root() / "users" / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def avatar_url_for_user(user: User, *, size: str = "small") -> str | None:
    """Public-facing URL: served by the /users/{id}/avatar endpoint."""
    small_path = getattr(user, "avatar_small", None)
    large_path = getattr(user, "avatar_large", None)
    has = (size == "small" and small_path) or (size == "large" and large_path)
    if not has:
        return None
    return f"/api/v1/users/{user.id}/avatar?size={size}"


def build_user_public(user: User) -> UserPublic:
    """Build a UserPublic from a User, including avatar URLs."""
    small = avatar_url_for_user(user, size="small")
    large = avatar_url_for_user(user, size="large")
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        timezone=user.timezone,
        created_at=user.created_at,
        email_verified=getattr(user, "email_verified", False) or False,
        avatar_url=small,
        avatar_url_small=small,
        avatar_url_large=large,
        theme=getattr(user, "theme", "light") or "light",
        institution=getattr(user, "institution", None),
    )


def update_profile(
    user: User,
    *,
    display_name: str | None,
    timezone: str | None,
    theme: str | None,
    institution: str | None,
) -> None:
    if display_name is not None:
        user.display_name = display_name.strip()[:120]
    if timezone is not None:
        user.timezone = timezone.strip()[:64] or "UTC"
    if theme is not None:
        if theme not in {"light", "dark"}:
            raise validation("theme must be 'light' or 'dark'.")
        user.theme = theme
    if institution is not None:
        user.institution = institution.strip()[:255] or None


def validate_and_avatar_from_upload(
    user: User, *, raw: bytes, max_bytes: int
) -> tuple[str, str]:
    """Validate bytes; downscale to small (64px) + large (256px); return
    (rel_small_path, rel_large_path) under avatar_local_root."""
    if len(raw) > max_bytes:
        raise validation(
            "Image too large.",
            code="avatar.too_large",
            details={"max_bytes": max_bytes},
        )
    fmt = detect_image_format(raw[:16])
    if fmt is None:
        raise validation(
            "File is not a supported image (PNG, JPEG, GIF, or WebP).",
            code="avatar.bad_type",
        )
    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()
    except Exception as e:
        raise validation("Image is corrupted.", code="avatar.corrupt") from e
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGBA")
    small = ImageOps.fit(
        img, (64, 64), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )
    large = ImageOps.fit(
        img, (256, 256), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )
    ud = _user_dir(user.id)
    small_path = ud / f"avatar-small.{fmt}"
    large_path = ud / f"avatar-large.{fmt}"
    # PIL uses 'JPEG' as the format key, not 'JPG'. Map our normalised
    # extension back to PIL's expected names.
    pil_format = {"jpg": "JPEG"}.get(fmt, fmt.upper())
    # JPEG doesn't support alpha. Flatten to white-on-RGB before saving.
    # PNG, GIF, WebP keep RGBA so transparent avatars stay transparent.
    if pil_format == "JPEG":
        small = small.convert("RGB")
        large = large.convert("RGB")
    small.save(small_path, format=pil_format, optimize=True)
    large.save(large_path, format=pil_format, optimize=True)
    for old in ud.glob("avatar-*.??*"):
        if old not in (small_path, large_path):
            try:
                old.unlink()
            except OSError:
                pass
    storage_root = _storage_root().resolve()
    rel_small = (
        str(small_path.resolve())
        .replace(str(storage_root), "")
        .lstrip("/\\")
        .replace("\\", "/")
    )
    rel_large = (
        str(large_path.resolve())
        .replace(str(storage_root), "")
        .lstrip("/\\")
        .replace("\\", "/")
    )
    return rel_small, rel_large


def avatar_path_for_user(user: User, *, size: str) -> Path | None:
    ud = _user_dir(user.id) if user.id else None
    if ud is None:
        return None
    pattern = "avatar-small.*" if size == "small" else "avatar-large.*"
    candidates = list(ud.glob(pattern))
    if not candidates:
        return None
    return candidates[0]


def read_avatar_bytes(user: User, *, size: str) -> tuple[bytes, str] | None:
    p = avatar_path_for_user(user, size=size)
    if p is None or not p.exists():
        return None
    return p.read_bytes(), _content_type_for_ext(p.suffix)


def _content_type_for_ext(suffix: str) -> str:
    s = suffix.lower().lstrip(".")
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(s, "application/octet-stream")
