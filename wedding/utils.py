#!/usr/bin/env python

import base64
from io import BytesIO

import qrcode
from django.urls import reverse


def generate_qr_code_data(invitation_code: str, fill_color: str = "black", back_color: str = "white") -> BytesIO:
    """
    Generates QR code image data in memory (BytesIO buffer) for a given code.
    Returns: BytesIO object containing PNG image data.
    """
    # 1. Build the full RSVP URL
    # IMPORTANT: Use your actual production domain for the final email send.
    domain = 'https://yourweddingdomain.com'
    url_path = reverse('rsvp', kwargs={'invitation_code': invitation_code})
    full_url = f'{domain}{url_path}'

    # 2. Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(full_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)

    # 3. Save image to BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0) # Rewind the buffer to the beginning

    return buffer


def generate_qr_code_data_uri(invitation_code: str, fill_color: str = "black", back_color: str = "white") -> str:
    """
    Generates a QR code for the given invitation code and returns it as a
    base64-encoded PNG data URI, suitable for embedding in an <image> tag.
    """
    buffer = generate_qr_code_data(invitation_code, fill_color=fill_color, back_color=back_color)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
