from django.contrib.gis.geos import Point
from rest_framework import serializers


class LatLngField(serializers.Field):
    default_error_messages = {
        "invalid": 'Expected an object like {{"lat": 19.13, "lng": 72.91}}.',
        "lat_range": "lat must be between -90 and 90.",
        "lng_range": "lng must be between -180 and 180.",
    }

    def to_representation(self, value):
        return {"lat": value.y, "lng": value.x}

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != {"lat", "lng"}:
            self.fail("invalid")

        try:
            lat = float(data["lat"])
            lng = float(data["lng"])
        except (TypeError, ValueError):
            self.fail("invalid")

        if not -90.0 <= lat <= 90.0:
            self.fail("lat_range")
        if not -180.0 <= lng <= 180.0:
            self.fail("lng_range")

        return Point(lng, lat, srid=4326)
