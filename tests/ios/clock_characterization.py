"""Finite-run affine clock constraints; never a hardware drift guarantee.

Causality requires alpha + beta*t1 <= t2 and alpha + beta*t4 >= t3.
Eliminating alpha yields a feasible beta interval without symmetric-delay assumptions.
A stable affine rate over the sampled run is an explicit model assumption.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Exchange:
    t1: float
    t2: float
    t3: float
    t4: float

    def __post_init__(self):
        if (any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0
                for v in (self.t1, self.t2, self.t3, self.t4))
                or not 0 <= self.t4 - self.t1 <= 1000 or self.t3 < self.t2):
            raise ValueError('Invalid exchange')


def rate_interval(rows, *, prior=(0.0, math.inf)):
    if not 1 <= len(rows) <= 80:
        raise ValueError('Bounded nonempty exchange list required')
    low, high = prior
    for a in rows:
        for b in rows:
            denominator, numerator = a.t4 - b.t1, a.t3 - b.t2
            if denominator > 0:
                low = max(low, numerator / denominator)
            elif denominator < 0:
                high = min(high, numerator / denominator)
            elif numerator > 0:
                raise ValueError('No affine clock consistent with exchanges')
    if not math.isfinite(high) or high <= 0 or low > high:
        raise ValueError('Clock-rate interval missing or inconsistent')
    return max(low, 0), high


class Characterization:
    def __init__(self):
        self.calibration = []
        self.holdout = []
        self.frozen = None
        self.failed = False

    def add(self, row):
        if self.failed:
            return
        if self.frozen is None:
            self.calibration.append(row)
            if len(self.calibration) == 20:
                if self.calibration[-1].t4 - self.calibration[0].t1 < 20_000:
                    self.failed = True
                    return
                try:
                    self.frozen = rate_interval(self.calibration)
                except ValueError:
                    self.failed = True
        elif len(self.holdout) < 60:
            self.holdout.append(row)
            try:
                rate_interval(self.calibration + self.holdout, prior=self.frozen)
            except ValueError:
                self.failed = True

    @property
    def candidate_ppm(self):
        if self.frozen is None or self.failed:
            return None
        return max(abs(v - 1) for v in self.frozen) * 1_000_000

    def summary(self):
        return dict(calibration_exchanges=len(self.calibration), holdout_exchanges=len(self.holdout),
            calibration_span_seconds=round((self.calibration[-1].t4-self.calibration[0].t1)/1000, 3) if self.calibration else 0,
            observed_affine_rate_ppm_interval=[round((v-1)*1_000_000, 3) for v in self.frozen] if self.frozen else None,
            candidate_absolute_drift_ppm=round(self.candidate_ppm, 3) if self.candidate_ppm is not None else None,
            holdout_consistent=not self.failed and len(self.holdout) >= 20,
            assumption='constant relative clock rate during sampled run', hardware_drift_limit_verified=False,
            production_drift_configured=False, receiver_guidance_eligible=False)
