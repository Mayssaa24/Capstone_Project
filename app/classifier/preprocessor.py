import io

from PIL import Image, UnidentifiedImageError

from app.errors import InvalidImageError


class ImagePreprocessor:
#Validates uploads

    def __init__(self, max_bytes=8 * 1024 * 1024, max_side=1024):
        self._max_bytes = max_bytes
        self._max_side = max_side
        self.initialize()

    def initialize(self):
        Image.MAX_IMAGE_PIXELS = 50_000_000  # guard against decompression bombs

    @property
    def max_bytes(self):
        return self._max_bytes

    @max_bytes.setter
    def max_bytes(self, value):
        if value <= 0:
            raise ValueError("max_bytes must be positive")
        self._max_bytes = value

    @property
    def max_side(self):
        return self._max_side

    @max_side.setter
    def max_side(self, value):
        if value < 32:
            raise ValueError("max_side must be at least 32")
        self._max_side = value

    def prepare(self, data):
        if not data:
            raise InvalidImageError("The uploaded file is empty.")
        if len(data) > self._max_bytes:
            raise InvalidImageError("Image is too large.", details={"max_bytes": self._max_bytes})
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise InvalidImageError("The file is not a valid image.") from exc
        image = image.convert("RGB")
        image.thumbnail((self._max_side, self._max_side))
        return image
