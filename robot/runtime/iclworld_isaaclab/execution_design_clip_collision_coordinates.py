"""Numerical conditioning of unchanged SHA-pinned iclworld_robot_40 collision vertices."""
import copy

SOURCES = {
    'iclworld_robot_40/clip_width_0.usda': 'fcfd2b76d9dbdb39197dce1bd08b63eceaa49e397754fb9fa92da7d736a49764',
    'iclworld_robot_40/clip_width_1.usda': '9105547efcd4ea23fc4a7243d61d58494dde877652690065bde34e308bd4d6c5',
    'iclworld_robot_40/clip_width_2.usda': '7746aea88bfcd0f0095a0e36d3fe853640905625284f9a9a062c039593f55ca4',
}
FACTOR = 100.
FIELD = 'reviewed_collision_coordinate_factor'


def verify_record(record):
    if (record.get('root_env') != 'ICLWORLD_EXECUTION_DESIGN_ASSETS'
            or SOURCES.get(record.get('relative_path')) != record.get('sha256')
            or record.get(FIELD) != FACTOR):
        raise ValueError('Exact source-bound iclworld_robot_40 collision coordinate conditioning required')


def configure_spec(spec):
    if spec.get('id') != 'iclworld_robot_40':
        raise ValueError('Collision coordinate pilot is limited to iclworld_robot_40')
    changed = []
    for mechanism in spec['mechanisms']:
        record = mechanism['mechanical_asset']
        if FIELD in record:
            raise ValueError('Existing collision coordinate override is not replaced')
        record[FIELD] = FACTOR
        verify_record(record)
        changed.append(mechanism['id'])
    if not changed:
        raise ValueError('Actual source iclworld_robot_40 mechanisms required')
    return changed


def verify_only_coordinate_change(old, new):
    from .engineering_checkpoint import PHYSICAL_KEYS
    if old.get('id') != 'iclworld_robot_40' or new.get('id') != 'iclworld_robot_40':
        raise ValueError('iclworld_robot_40 coordinate migration task identity mismatch')
    expected = copy.deepcopy(old)
    changed = configure_spec(expected)
    if any(expected.get(k) != new.get(k) for k in PHYSICAL_KEYS):
        raise ValueError('iclworld_robot_40 coordinate migration changed another physical input')
    return changed


def apply(stage, prefix, source_path, record):
    verify_record(record)
    from .author_collision_coordinates import prepare, verify
    prepared = prepare(stage, prefix, source_path, FACTOR)
    if not prepared:
        raise ValueError('iclworld_robot_40 actual source collision meshes were not found')
    return verify(stage, prepared, FACTOR)
