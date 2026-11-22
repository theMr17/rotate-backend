import logging

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from django.conf import settings

from .exceptions import ImageStorageNotConfigured, ImageUploadFailed

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = ['jpg', 'png', 'webp']

def _configure():
	config = settings.CLOUDINARY
	if not all(config.get(key) for key in ('cloud_name', 'api_key', 'api_secret')):
		raise ImageStorageNotConfigured()
	cloudinary.config(**config)


def build_folder(subfolder):
	root = settings.CLOUDINARY_ROOT_FOLDER.strip('/')
	return f'{root}/{subfolder}' if root else subfolder


def upload_image(file, *, folder, public_id=None, transformation=None):
	"""Upload ``file`` to Cloudinary and return ``(secure_url, public_id)``.

	Pass a fixed ``public_id`` to replace an existing image in place (one image
	per owner, e.g. a profile photo). Leave it ``None`` to let Cloudinary
	generate a unique id (many images per owner, e.g. item gallery).
	"""
	_configure()
	options = {
		'folder': folder,
		'resource_type': 'image',
		'allowed_formats': ALLOWED_FORMATS,
	}
	if public_id:
		options.update(public_id=public_id, overwrite=True, invalidate=True)
	if transformation:
		options['transformation'] = transformation

	try:
		result = cloudinary.uploader.upload(file, **options)
	except CloudinaryError as exc:
		logger.warning('Cloudinary upload to %s failed: %s', folder, exc)
		raise ImageUploadFailed() from exc
	return result['secure_url'], result['public_id']


def delete_image(public_id):
	"""Remove an image from Cloudinary. Failures are logged, not raised."""
	if not public_id:
		return
	try:
		_configure()
		cloudinary.uploader.destroy(public_id, invalidate=True, resource_type='image')
	except (ImageStorageNotConfigured, CloudinaryError) as exc:
		logger.warning('Could not delete Cloudinary image %s: %s', public_id, exc)
