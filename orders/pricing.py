"""Rental price calculation.

Used both for quotes (before a request exists) and for the snapshot taken when an
order is accepted, so the two always agree for the same inputs.
"""
import math
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

PAISE = Decimal('0.01')
SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class PriceBreakdown:
    billable_hours: int
    hourly_rate: Decimal
    rental_fee: Decimal
    platform_fee_percent: Decimal
    platform_fee: Decimal
    deposit: Decimal
    total_due: Decimal

    def as_dict(self):
        return asdict(self)


def _money(value):
    return Decimal(value).quantize(PAISE, rounding=ROUND_HALF_UP)


def billable_hours(start_time, end_time):
    """Whole hours charged for the period; any started hour counts as a full hour."""
    seconds = (end_time - start_time).total_seconds()
    if seconds <= 0:
        raise ValueError('End time must be after start time.')
    return math.ceil(seconds / SECONDS_PER_HOUR)


def platform_fee_percent():
    return Decimal(str(settings.PLATFORM_FEE_PERCENT))

def calculate(hourly_rate, start_time, end_time, deposit=Decimal('0')):
    hours = billable_hours(start_time, end_time)
    rate = _money(hourly_rate)
    percent = platform_fee_percent()
    rental_fee = _money(rate * hours)
    platform_fee = _money(rental_fee * percent / 100)
    deposit = _money(deposit or 0)
    return PriceBreakdown(
        billable_hours=hours,
        hourly_rate=rate,
        rental_fee=rental_fee,
        platform_fee_percent=percent,
        platform_fee=platform_fee,
        deposit=deposit,
        total_due=rental_fee + platform_fee + deposit,
    )
