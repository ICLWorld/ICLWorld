"""iclworld_robot_46 v3 requires measured blade insertion followed by a hand-free lift.

Reuse the native geometry/contact witness without widening the iclworld_robot_28 task gate.
This applies to formal evaluation as well as independent engineering references.
"""
from .execution_design_robot_28_scoop import ScoopWitness, REVISION


def enabled(spec):
    return spec.get('id') == 'iclworld_robot_46' and spec.get('execution_design', {}).get('revision') == REVISION


__all__ = ['ScoopWitness', 'REVISION', 'enabled']
