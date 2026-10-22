"""Bounded local image inspection, deliberately not OCR."""
import warnings
from eduagent.documents.models import DocumentError, result, unit


def image_bytes(path):
    from PIL import Image, ImageOps
    from io import BytesIO
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            with Image.open(path) as im:
                if im.width * im.height > 16_000_000 or getattr(im, 'n_frames', 1) != 1:
                    raise DocumentError('document_too_large', 413)
                im.load()
                image = ImageOps.exif_transpose(im).convert('RGB')
                size = image.size
                image.thumbnail((1800,1800))
                out = BytesIO(); image.save(out, format='PNG')
                raw = out.getvalue()
                if len(raw)>2*1024*1024: raise DocumentError('document_too_large',413)
                return raw,size
        except DocumentError: raise
        except Exception: raise DocumentError('invalid_document') from None


def extract(path, kind):
    raw,(width,height)=image_bytes(path)
    return result([unit(1,'image','图片原件','',dict(image_number=1,width=width,height=height,region=[0,0,width,height]),
                        warnings=['image_requires_transcription','visual_accuracy_not_verified'])],['no_local_ocr'])
