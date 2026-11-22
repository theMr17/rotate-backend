from uploads import build_folder, delete_image, upload_image

SUBFOLDER = 'condition_photos'

TRANSFORMATION = [
	{'width': 1600, 'height': 1600, 'crop': 'limit'},
	{'quality': 'auto'},
]


def upload_condition_photo(order, stage, file):
	return upload_image(
		file,
		folder=build_folder(f'{SUBFOLDER}/order_{order.pk}/{stage}'),
		transformation=TRANSFORMATION,
	)


def delete_condition_photo(public_id):
	delete_image(public_id)
