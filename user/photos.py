from uploads import build_folder, delete_image, upload_image

SUBFOLDER = 'profile_photos'

TRANSFORMATION = [
	{'width': 512, 'height': 512, 'crop': 'fill', 'gravity': 'face'},
	{'quality': 'auto'},
]


def upload_profile_photo(user, file):
	return upload_image(
		file,
		folder=build_folder(SUBFOLDER),
		public_id=f'user_{user.pk}',
		transformation=TRANSFORMATION,
	)


def delete_profile_photo(public_id):
	delete_image(public_id)
