from django.conf import settings
from rest_framework import serializers

ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

class ImageUploadField(serializers.FileField):
	"""A multipart file field that accepts JPEG/PNG/WebP up to a size limit."""

	default_error_messages = {
		'invalid_image_type': 'Upload a JPEG, PNG or WebP image.',
		'image_too_large': 'Image must be {max_mb} MB or smaller.',
	}

	def __init__(self, *, max_bytes=None, **kwargs):
		self.max_bytes = max_bytes
		super().__init__(**kwargs)

	def to_internal_value(self, data):
		file = super().to_internal_value(data)
		if getattr(file, 'content_type', None) not in ALLOWED_CONTENT_TYPES:
			self.fail('invalid_image_type')
		max_bytes = self.max_bytes or settings.IMAGE_UPLOAD_MAX_BYTES
		if file.size > max_bytes:
			self.fail('image_too_large', max_mb=max_bytes // (1024 * 1024))
		return file
