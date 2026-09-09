from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
	"""Return a lightweight liveness response without touching the database."""
	return JsonResponse({'status': 'ok'})
