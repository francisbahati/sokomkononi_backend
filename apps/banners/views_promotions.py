"""
DEPRECATED — this module was a broken duplicate of views.py's
CampaignViewSet / PromotionsAnalyticsView. It has been reduced to
import shims so old references (urls_promotions, external imports)
keep resolving while the real implementations live in views.py.
"""
from .views import (  # noqa: F401
    BannerAdViewSet,
    CampaignViewSet,
    PromotionsAnalyticsView,
)

__all__ = ["BannerAdViewSet", "CampaignViewSet", "PromotionsAnalyticsView"]
