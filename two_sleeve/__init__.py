"""two_sleeve: a learning-first, two-sleeve crypto trading system.

Sleeve 1 ("carry", 80% of capital): delta-neutral funding-rate harvesting —
long spot, short perp, collect funding. Targets high-single-digit annualized
yield with minimal price exposure.

Sleeve 2 ("venture", 20% of capital): small, strictly-capped high-risk trades
(momentum breakouts, funding-extreme fades) that are allowed to lose the whole
sleeve in a month. This sleeve exists to learn, not to earn.

The default mode is ADVISOR: the tools scan markets and print exactly what to
do in the exchange UI. Nothing trades your money unless you explicitly wire up
live execution and understand what it does.
"""

__version__ = "0.1.0"
