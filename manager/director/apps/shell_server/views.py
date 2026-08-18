# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import time

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..sites.models import Site
from ..users.models import User
from .helpers import authenticate_kinit, generate_token


def sites_response(user: User) -> JsonResponse:
    sites = {}
    # Deliberately return only direct memberships. The broader filter_for_user()
    # includes every site for superusers, which is unwieldy in an SSH selector.
    for site in Site.objects.filter(users=user):
        token = generate_token(site, expire_time=time.time() + 60)

        sites[site.name] = [site.id, token.decode("latin-1")]

    return JsonResponse(sites, status=200)


@csrf_exempt
@require_POST
def authenticate_view(request: HttpRequest) -> HttpResponse:
    if any(key not in request.POST for key in ["username", "password"]):
        return HttpResponse(status=400)

    username = request.POST["username"]

    user = authenticate_kinit(username, request.POST["password"])

    if user is None:
        return HttpResponse(status=401)

    return sites_response(user)


@csrf_exempt
@require_POST
def sites_view(request: HttpRequest) -> HttpResponse:
    """Return sites after the shell host has authenticated a user with IPA."""
    if "username" not in request.POST:
        return HttpResponse(status=400)

    try:
        user = get_user_model().objects.get(username=request.POST["username"])
    except get_user_model().DoesNotExist:
        return HttpResponse(status=401)

    return sites_response(user)
