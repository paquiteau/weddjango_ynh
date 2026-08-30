from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from pypdf import PdfReader, PdfWriter, Transformation

from .models import Group, InvitationTier
from .utils import generate_qr_code_data_uri

# ISO A4, in points (1mm = 72/25.4 pt).
_MM_TO_PT = 72 / 25.4
A4_WIDTH_PT = 297 * _MM_TO_PT
A4_HEIGHT_PT = 210 * _MM_TO_PT

# Matches the invite artwork's brand green (see the templates' `fill:#4c6244`).
QR_CODE_COLOR = "#333333"

# The printer's own margin handling shifts each rotated page slightly within
# its half of the sheet; on the counter-clockwise (odd-numbered) invite this
# lands 2mm off after cutting, so nudge it down (in sheet space, post-rotation)
# to compensate. Purely a print-registration fudge factor.
_ODD_INVITE_PRINT_SHIFT_PT = 2 * _MM_TO_PT

# Placeholder the invite artwork marks with `inkscape:label="QRCODE"`: a plain
# `<rect id="qrcode" .../>`, kept free of any `href` so Inkscape can open and
# re-export the artwork without choking on a non-URI attribute value. Its
# geometry is taken as-is (so moving/resizing it in Inkscape just works) and
# swapped for a live `<image>` of the generated QR code after rendering.
_QRCODE_RECT_RE = re.compile(r'<rect\b(?:(?!/>).)*?id="qrcode"(?:(?!/>).)*?/>', re.S)
_ATTR_RE = re.compile(r'([\w:-]+)="([^"]*)"')


def _embed_qr_code(svg_string: str, qr_data_uri: str) -> str:
    """Replaces the invite artwork's `qrcode` placeholder rect with the QR image."""
    match = _QRCODE_RECT_RE.search(svg_string)
    if match is None:
        raise ValueError("invite template has no `<rect id=\"qrcode\">` placeholder")
    attrs = dict(_ATTR_RE.findall(match.group()))
    image_tag = (
        f'<image x="{attrs["x"]}" y="{attrs["y"]}" '
        f'width="{attrs["width"]}" height="{attrs["height"]}" '
        f'preserveAspectRatio="xMidYMid meet" href="{qr_data_uri}" />'
    )
    return svg_string[: match.start()] + image_tag + svg_string[match.end() :]

# Maps each invitation tier to the SVG template rendering its invite design.
TIER_TEMPLATE_MAP: dict[str, str] = {
    InvitationTier.FAIRE_PART: "wedding/invites/tier_faire_part.svg",
    InvitationTier.MESSE: "wedding/invites/tier_messe.svg",
    InvitationTier.COCKTAIL: "wedding/invites/tier_cocktail.svg",
    InvitationTier.REPAS: "wedding/invites/tier_repas.svg",
    InvitationTier.MAIRIE: "wedding/invites/tier_mairie.svg",
}


def render_invite_svg(group: Group) -> str:
    """Renders the invite SVG template for a group's tier, with its QR code."""
    template_name = TIER_TEMPLATE_MAP[group.invitation_tier]

    url_path = reverse("rsvp", kwargs={"invitation_code": group.invitation_code})
    rsvp_url = f"{settings.SITE_DOMAIN}{url_path}"

    context = {
        "group": group,
        "guests": group.guests.all(),
        "rsvp_url": rsvp_url,
    }
    svg_string = render_to_string(template_name, context)
    qr_data_uri = generate_qr_code_data_uri(
        group.invitation_code, fill_color=QR_CODE_COLOR, back_color="transparent"
    )
    return _embed_qr_code(svg_string, qr_data_uri)


def svg_to_pdf_bytes(svg_string: str) -> bytes:
    """
    Converts a rendered SVG document into a single-page PDF, via Inkscape's
    CLI, with fonts embedded (subsetted to the glyphs used) rather than
    converted to paths — text-to-path multiplies the page's vector
    complexity enough to make color print drivers fall back to a low-res
    internal raster.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        svg_path = Path(tmp_dir) / "invite.svg"
        pdf_path = Path(tmp_dir) / "invite.pdf"
        svg_path.write_text(svg_string, encoding="utf-8")
        subprocess.run(
            [
                "inkscape",
                "--export-type=pdf",
                f"--export-filename={pdf_path}",
                str(svg_path),
            ],
            check=True,
            capture_output=True,
        )
        return pdf_path.read_bytes()


def _add_sheet(writer: PdfWriter, left_page, right_page) -> None:
    """
    Lays out one or two A5-landscape invite pages onto a single A4-landscape
    sheet, unscaled, joined on their bottom edges: the left invite is rotated
    90° counter-clockwise and the right invite 90° clockwise, so that after
    the sheet is cut in half the trimmed edge of each invite is the one that
    started life as its bottom (kept clear of content) rather than a printer
    margin.
    """
    sheet = writer.add_blank_page(width=A4_WIDTH_PT, height=A4_HEIGHT_PT)

    invite_w = float(left_page.mediabox.width)
    invite_h = float(left_page.mediabox.height)
    block_w = 2 * invite_h
    block_h = invite_w
    offset_x = (A4_WIDTH_PT - block_w) / 2
    offset_y = (A4_HEIGHT_PT - block_h) / 2

    left_transform = (
        Transformation()
        .rotate(90)
        .translate(invite_h + offset_x, offset_y - _ODD_INVITE_PRINT_SHIFT_PT)
    )
    sheet.merge_transformed_page(left_page, left_transform)

    if right_page is not None:
        right_transform = (
            Transformation()
            .rotate(-90)
            .translate(invite_h + offset_x, invite_w + offset_y)
        )
        sheet.merge_transformed_page(right_page, right_transform)


def generate_invitations_pdf(groups: Iterable[Group]) -> bytes:
    """
    Renders one A5-landscape invite per group (skipping tiers without a
    template) and lays them out two-up on A4-landscape sheets, unscaled and
    joined on their bottom edges, ready to print and cut in half.
    """
    writer = PdfWriter()
    pending = None

    for group in groups:
        if group.invitation_tier not in TIER_TEMPLATE_MAP:
            continue
        svg_string = render_invite_svg(group)
        pdf_bytes = svg_to_pdf_bytes(svg_string)
        page = PdfReader(BytesIO(pdf_bytes)).pages[0]

        if pending is None:
            pending = page
        else:
            _add_sheet(writer, pending, page)
            pending = None

    if pending is not None:
        _add_sheet(writer, pending, None)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
