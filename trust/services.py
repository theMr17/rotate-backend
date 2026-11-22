from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q

from orders.models import Order

from .models import ReliabilityStats, Review

RELIABILITY_LEVELS = [(90, 'excellent'), (75, 'good'), (50, 'fair'), (0, 'poor')]


class ReviewError(Exception):
    pass


def _reviewee_and_role(order, user):
    if user.pk == order.borrower_id:
        return order.lender, Review.Role.LENDER
    if user.pk == order.lender_id:
        return order.borrower, Review.Role.BORROWER
    return None, None


def review_blocker(order, user):
    reviewee, _ = _reviewee_and_role(order, user)
    if reviewee is None:
        return 'Only the borrower or lender of this order can review it.'
    if order.status != Order.Status.COMPLETED:
        return 'You can review an order only after it is completed.'
    if Review.objects.filter(order=order, reviewer=user).exists():
        return 'You have already reviewed this order.'
    return None


def create_review(order, reviewer, rating, comment=''):
    blocker = review_blocker(order, reviewer)
    if blocker:
        raise ReviewError(blocker)
    reviewee, role = _reviewee_and_role(order, reviewer)
    try:
        with transaction.atomic():
            return Review.objects.create(
                order=order,
                reviewer=reviewer,
                reviewee=reviewee,
                reviewee_role=role,
                rating=rating,
                comment=comment,
            )
    except IntegrityError:
        raise ReviewError('You have already reviewed this order.')


def _average(value):
    return round(float(value), 1) if value is not None else None


def rating_summary(user):
    lender = Q(reviewee_role=Review.Role.LENDER)
    borrower = Q(reviewee_role=Review.Role.BORROWER)
    stats = Review.objects.filter(reviewee=user).aggregate(
        average=Avg('rating'),
        count=Count('id'),
        lender_average=Avg('rating', filter=lender),
        lender_count=Count('id', filter=lender),
        borrower_average=Avg('rating', filter=borrower),
        borrower_count=Count('id', filter=borrower),
    )
    return {
        'average': _average(stats['average']),
        'count': stats['count'],
        'as_lender': {'average': _average(stats['lender_average']), 'count': stats['lender_count']},
        'as_borrower': {
            'average': _average(stats['borrower_average']),
            'count': stats['borrower_count'],
        },
    }


def reliability_level(score):
    if score is None:
        return 'new'
    return next(level for threshold, level in RELIABILITY_LEVELS if score >= threshold)


def reliability_summary(user):
    stats = ReliabilityStats.objects.filter(user=user).first() or ReliabilityStats(user=user)
    return {
        'score': stats.score,
        'level': reliability_level(stats.score),
        'rentals_counted': stats.rentals_counted,
        'on_time_returns': stats.on_time_returns,
        'late_returns': stats.late_returns,
        'late_cancellations': stats.late_cancellations,
    }


def trust_summary(user):
    return {'rating': rating_summary(user), 'reliability': reliability_summary(user)}
