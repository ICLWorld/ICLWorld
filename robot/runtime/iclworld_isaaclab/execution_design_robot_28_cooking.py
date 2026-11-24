"""Source-faithful iclworld_robot_28 spatula; retain its original triangles and all tasks."""
import copy

SOURCE_SHA='80783d541400ad8ff889274efcecca551e08c9b12c28004427922e1a0a4f0966'


def configure_spec(spec):
    if spec.get('id')!='iclworld_robot_28':raise ValueError('iclworld_robot_28 source spatula cooking only')
    tool=next(o for o in spec['objects']if o['id']=='spatula')
    if tool.get('source_asset',{}).get('sha256')!=SOURCE_SHA or tool.get('reviewed_collision_settings'):
        raise ValueError('Unmodified SHA-pinned original iclworld_robot_28 spatula required')
    tool['reviewed_collision_settings']=dict(source_sha256=SOURCE_SHA,approximation='sdf',sdf_resolution=384)
    return ['spatula']


def verify_only_cooking_change(old,new):
    from .engineering_checkpoint import PHYSICAL_KEYS
    expected=copy.deepcopy(old);changed=configure_spec(expected)
    if new.get('id')!='iclworld_robot_28'or any(expected.get(k)!=new.get(k)for k in PHYSICAL_KEYS):
        raise ValueError('iclworld_robot_28 fidelity migration changed another physical input')
    return changed
