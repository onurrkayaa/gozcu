"""Goruntu alim mantigi. View'dan bagimsiz, dogrudan test edilebilir."""
import hashlib
from datetime import datetime, timezone as dt_timezone

from django.db import IntegrityError, transaction
from PIL import ExifTags, Image, UnidentifiedImageError

from .models import Frame

CHUNK_SIZE = 64 * 1024


class InvalidImageError(Exception):
    """Yuklenen dosya gecerli bir goruntu degil."""


def compute_sha256(uploaded_file):
    """Dosyayi parca parca okuyarak ozetini hesaplar; tamamini bellege almaz."""
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in iter(lambda: uploaded_file.read(CHUNK_SIZE), b""):
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _dms_to_degrees(dms, ref):
    """EXIF'in derece/dakika/saniye ucluusunu ondalik dereceye cevirir."""
    try:
        degrees, minutes, seconds = (_to_float(v) for v in dms)
    except (TypeError, ValueError):
        return None
    if None in (degrees, minutes, seconds):
        return None
    result = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        result = -result
    return result


def extract_exif(image):
    """EXIF'ten cekim zamani ve GPS bilgisini cikarir. Yoksa hepsi None doner."""
    empty = {"captured_at": None, "latitude": None, "longitude": None, "altitude_m": None}
    try:
        exif = image.getexif()
    except Exception:
        return empty
    if not exif:
        return empty

    result = dict(empty)

    try:
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    except Exception:
        exif_ifd = {}
    raw_dt = exif_ifd.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
    if raw_dt:
        try:
            # EXIF zamani yerel saat kabul edilir; USE_TZ acik oldugu icin UTC'ye baglıyoruz.
            naive = datetime.strptime(str(raw_dt).strip(), "%Y:%m:%d %H:%M:%S")
            result["captured_at"] = naive.replace(tzinfo=dt_timezone.utc)
        except ValueError:
            pass

    try:
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        gps = {}
    if gps:
        lat = gps.get(ExifTags.GPS.GPSLatitude)
        lat_ref = gps.get(ExifTags.GPS.GPSLatitudeRef)
        lon = gps.get(ExifTags.GPS.GPSLongitude)
        lon_ref = gps.get(ExifTags.GPS.GPSLongitudeRef)
        if lat and lon:
            result["latitude"] = _dms_to_degrees(lat, lat_ref)
            result["longitude"] = _dms_to_degrees(lon, lon_ref)
        altitude = _to_float(gps.get(ExifTags.GPS.GPSAltitude))
        if altitude is not None:
            # GPSAltitudeRef == 1 ise deniz seviyesinin altini gosterir.
            if gps.get(ExifTags.GPS.GPSAltitudeRef) in (1, b"\x01"):
                altitude = -altitude
            result["altitude_m"] = altitude

    return result


def read_image_metadata(uploaded_file):
    """Boyutlari ve EXIF'i DOSYADAN okur; istemciden gelen degerlere guvenmez."""
    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as probe:
            probe.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise InvalidImageError("Dosya gecerli bir goruntu degil.") from exc

    # verify() nesneyi tuketir; olculer ve EXIF icin dosyayi yeniden aciyoruz.
    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as image:
            width, height = image.size
            metadata = extract_exif(image)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("Dosya gecerli bir goruntu degil.") from exc
    finally:
        uploaded_file.seek(0)

    metadata["width"] = width
    metadata["height"] = height
    return metadata


def ingest_frame(mission, uploaded_file):
    """Bir dosyayi goreve ekler. (frame, duplicate) doner.

    Ayni gorevde ayni sha256 varsa yeni kayit olusturmaz, mevcut olani dondurur.
    """
    sha256 = compute_sha256(uploaded_file)
    existing = Frame.objects.filter(mission=mission, sha256=sha256).first()
    if existing is not None:
        return existing, True

    metadata = read_image_metadata(uploaded_file)

    try:
        with transaction.atomic():
            frame = Frame.objects.create(
                mission=mission,
                image=uploaded_file,
                original_filename=uploaded_file.name,
                sha256=sha256,
                width=metadata["width"],
                height=metadata["height"],
                captured_at=metadata["captured_at"],
                latitude=metadata["latitude"],
                longitude=metadata["longitude"],
                altitude_m=metadata["altitude_m"],
                status=Frame.Status.PENDING,
            )
    except IntegrityError:
        # Es zamanli iki yukleme yarisirsa tekillik kisiti burada devreye girer.
        frame = Frame.objects.get(mission=mission, sha256=sha256)
        return frame, True

    return frame, False
