from pathlib import Path

from django.conf import settings
from django.http import HttpResponse


def service_worker(request):
    path = Path(settings.BASE_DIR) / "static" / "pwa" / "service-worker.js"

    response = HttpResponse(
        path.read_text(encoding="utf-8"),
        content_type="application/javascript",
    )

    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"

    return response
