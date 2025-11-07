#!/usr/bin/env python

import qrcode
from io import BytesIO
from django.urls import reverse

def generate_qr_code_data(invitation_code:str) -> BytesIO:
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

    img = qr.make_image(fill_color="black", back_color="white")
    
    # 3. Save image to BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0) # Rewind the buffer to the beginning
    
    return buffer
