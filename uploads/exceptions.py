from rest_framework import status
from rest_framework.exceptions import APIException

class ImageStorageNotConfigured(APIException):
	status_code = status.HTTP_503_SERVICE_UNAVAILABLE
	default_detail = 'Image uploads are not configured on the server.'
	default_code = 'image_storage_not_configured'


class ImageUploadFailed(APIException):
	status_code = status.HTTP_502_BAD_GATEWAY
	default_detail = 'Could not upload the image. Please try another image.'
	default_code = 'image_upload_failed'

