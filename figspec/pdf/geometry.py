"""2D affine transforms, PDF row-vector convention: (x,y) -> (a*x+c*y+e, b*x+d*y+f)."""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class Mat:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @classmethod
    def from_seq(cls, seq) -> "Mat":
        a, b, c, d, e, f = (float(v) for v in seq)
        return cls(a, b, c, d, e, f)

    def __matmul__(self, o: "Mat") -> "Mat":
        # self applied first, then o (row vectors: v' = v @ self @ o)
        return Mat(
            self.a * o.a + self.b * o.c,
            self.a * o.b + self.b * o.d,
            self.c * o.a + self.d * o.c,
            self.c * o.b + self.d * o.d,
            self.e * o.a + self.f * o.c + o.e,
            self.e * o.b + self.f * o.d + o.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def vertical_scale(self) -> float:
        return math.hypot(self.c, self.d)

    def singular_values(self) -> tuple[float, float]:
        t = self.a * self.a + self.b * self.b + self.c * self.c + self.d * self.d
        det = self.a * self.d - self.b * self.c
        root = math.sqrt(max(t * t - 4 * det * det, 0.0))
        return (math.sqrt(max((t + root) / 2, 0.0)), math.sqrt(max((t - root) / 2, 0.0)))
