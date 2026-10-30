"""Volume batch namespace: `pyta.batch.volume.<indicator>`."""

from pyta.indicators.volume.ad import ad_batch as ad
from pyta.indicators.volume.obv import obv_batch as obv

__all__ = ["ad", "obv"]
