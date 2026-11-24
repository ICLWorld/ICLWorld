"""Source-design input changes, applied only during fresh world construction.

No live-state writes. Layout authoring is not physics acceptance: every output
remains release-blocked until its native positive/negative controls pass.
"""
from copy import deepcopy
import hashlib
import json
import math
from .execution_design import build_task_contract, metadata, WORKFLOW_TASKS

REVISION = 'embodied50-execution-v3-20261102'
REPLAY_RELOCATE_TASKS = frozenset(('iclworld_robot_12','iclworld_robot_29','iclworld_robot_37','iclworld_robot_44','iclworld_robot_47','iclworld_robot_48','iclworld_robot_49','iclworld_robot_50'))
# Identity-preserving permutations of actual source object positions. Groups
# are explicit so containers, tools, fixtures and supporting bodies do not get
# exchanged with cargo of incompatible geometry.
LAYOUT_GROUPS = {
    'iclworld_robot_02': ('blocks',), 'iclworld_robot_03': ('cups',), 'iclworld_robot_06': ('balls',),
    'iclworld_robot_08': ('shoes',), 'iclworld_robot_10': ('pieces',), 'iclworld_robot_11': ('blocks',),
    'iclworld_robot_18': ('balls',), 'iclworld_robot_19': ('bottles','caps'), 'iclworld_robot_21': ('blocks',),
    'iclworld_robot_23': ('cups',), 'iclworld_robot_24': ('cups',), 'iclworld_robot_25': ('cutlery',),
    'iclworld_robot_27': ('cutlery',), 'iclworld_robot_28': ('foods',), 'iclworld_robot_33': ('bottles',),
    'iclworld_robot_34': ('cutlery',), 'iclworld_robot_36': ('balls',), 'iclworld_robot_38': ('rings',),
    'iclworld_robot_42': ('balls',),
}
SPECIAL = frozenset(('iclworld_robot_04','iclworld_robot_05','iclworld_robot_07','iclworld_robot_13','iclworld_robot_14','iclworld_robot_15','iclworld_robot_16','iclworld_robot_22',
                     'iclworld_robot_26','iclworld_robot_30','iclworld_robot_31','iclworld_robot_32','iclworld_robot_35','iclworld_robot_40','iclworld_robot_41','iclworld_robot_43','iclworld_robot_45','iclworld_robot_46'))
IMPLEMENTED = frozenset(LAYOUT_GROUPS) | SPECIAL | REPLAY_RELOCATE_TASKS | WORKFLOW_TASKS
assert IMPLEMENTED == {f'iclworld_robot_{n:02}' for n in range(1,51)}


def condition_capability_v3(task, condition):
    if condition not in metadata(task, revision=REVISION)['support_mask']:
        return dict(implemented=False, reason='unsupported_by_source_design')
    return dict(implemented=True, adapter='execution_workflow_scenes' if task in WORKFLOW_TASKS else 'explicit_inputs_v3',
                physics_validated=False, release_ready=False)


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def physical_input_signature(spec):
    """Exclude render-only properties and run identity, include actual targets."""
    fields=('objects','zones','mechanisms','semantic','goals')
    if ((spec.get('id')=='iclworld_robot_44'and spec.get('semantic',{}).get('execution_design_fold_fixture'))
            or(spec.get('id')=='iclworld_robot_47'and spec.get('semantic',{}).get('execution_design_flip_fixture'))):fields+=('fixtures',)
    return _hash({k:spec.get(k)for k in fields})


def _cycle(items, seed, fields=('xy',)):
    if len(items) < 2:
        raise ValueError('An input permutation needs at least two objects')
    offset = 1 + seed % (len(items)-1)
    old = [{k:deepcopy(o[k]) for k in fields} for o in items]
    for i,o in enumerate(items):o.update(deepcopy(old[(i+offset)%len(items)]))
    return offset


def _group(spec, name):
    ids=spec['semantic']['groups'][name];objects={o['id']:o for o in spec['objects']}
    return [objects[n] for n in ids]


def _update_grid_mapping(spec):
    objects=_group(spec,'blocks')
    # Operator coordinates: far=+X, left=+Y, same as native grid().
    rows=[sorted(objects,key=lambda o:o['xy'][0],reverse=True)[:2],
          sorted(objects,key=lambda o:o['xy'][0],reverse=True)[2:]]
    grid=[[o['id'] for o in sorted(row,key=lambda o:o['xy'][1],reverse=True)]for row in rows]
    if spec['variant']=='B':grid=[list(row)for row in zip(*grid[::-1])]
    elif spec['variant']=='C':grid=[row[::-1]for row in grid]
    cells=spec['semantic']['grid_cells'];mapping={grid[r][c]:cells[r][c]for r in range(2)for c in range(2)}
    spec['semantic']['mapping']=mapping
    for goal in spec['goals']:
        if goal.get('object') in mapping:goal['target']=mapping[goal['object']]


def _update_layout_transfer(spec):
    pieces=_group(spec,'pieces');tray=next(o for o in spec['objects']if o['id']=='tray')
    center=[sum(o['xy'][i]for o in pieces)/len(pieces)for i in range(2)]
    targets={}
    for o in pieces:
        rel=[o['xy'][i]-center[i]for i in range(2)]
        if spec['variant']=='C':rel[0]*=-1
        targets[o['id']]=dict(xy=[tray['xy'][i]+rel[i]for i in range(2)],
                              yaw=o.get('yaw',0)+(math.pi/2 if spec['variant']=='B'else 0))
    spec['semantic']['targets']=targets
    for z in spec['zones']:
        name=z['id'].removesuffix('_target')
        if name in targets:z['xy']=deepcopy(targets[name]['xy'])
    for g in spec['goals']:
        if g.get('object') in targets:g['yaw']=targets[g['object']]['yaw']


def _update_stack_goals(spec):
    objects={o['id']:o for o in spec['objects']};zones={z['id']:z for z in spec['zones']}
    if spec['id']=='iclworld_robot_14':
        initial=sorted(objects,key=lambda n:objects[n]['bottom'],reverse=True)
        desired=initial[:]
        if spec['variant']=='A':desired[0],desired[1]=desired[1],desired[0]
        elif spec['variant']=='B':desired[1],desired[2]=desired[2],desired[1]
        else:desired.reverse()
        goals=[dict(type='place',object=n,target='stage_'+n)for n in initial]
        height=.8;previous='table'
        for n in desired[::-1]:
            zones['rebuild_'+n]['surface_z']=height
            goals.append(dict(type='place',object=n,target='rebuild_'+n,required_support=previous))
            height+=2*objects[n]['size'][2];previous=n
        spec['goals']=goals
    else:
        height=.8
        for g in spec['goals']:
            zones[g['target']]['surface_z']=height
            height+=2*objects[g['object']]['size'][2]


def _update_swap_goals(spec):
    objects=_group(spec,'blocks');other={objects[0]['id']:objects[1],objects[1]['id']:objects[0]}
    zones={z['id']:z for z in spec['zones']};targets={}
    for o in objects:
        target=other[o['id']]if spec['variant']in('A','C')else o
        orientation=other[o['id']]if spec['variant']in('B','C')else o
        zones[o['id']+'_target']['xy']=deepcopy(target['xy']);targets[o['id']]=orientation['yaw']
    for g in spec['goals']:
        # Temporary staging is not the final swapped orientation.
        if g['target']!='temporary':g['yaw']=targets[g['object']]
        else:g['yaw']=next(o['yaw']for o in objects if o['id']==g['object'])


def _input(spec, seed):
    task=spec['id'];objects={o['id']:o for o in spec['objects']};sem=spec['semantic']
    change=dict(kind='task_specific_input', operations=[])
    ops=change['operations']
    if task in LAYOUT_GROUPS:
        for group in LAYOUT_GROUPS[task]:
            members=_group(spec,group);offset=_cycle(members,seed)
            ops.append(dict(kind='object_position_derangement',group=group,offset=offset,objects=[o['id']for o in members]))
        if task=='iclworld_robot_11':_update_grid_mapping(spec)
        # iclworld_robot_06 moves the whole six-hole fixture slightly while retaining its
        # topology and operator-left reference; balls were separately shuffled.
        if task=='iclworld_robot_06':
            dx=(-.025,.025,.04)[seed%3];objects['eggtray']['xy'][0]+=dx
            for z in spec['zones']:z['xy'][0]+=dx
            # Native iclworld_robot_06 cells are expressed in task coordinates. Move their
            # physical cavity floors with the actual fixture, not only the
            # expert's placement zones; retain every radius/floor threshold.
            for cell in sem['cells'].values():cell['center'][0]+=dx
            ops.append(dict(kind='tray_initial_position',dx=dx))
    elif task in ('iclworld_robot_04','iclworld_robot_05'):
        movable=[o for o in spec['objects']if o.get('role')!='fixture']
        regions=[z for z in spec['zones']if z.get('shape')in ('triangle','square','circle')]
        if len(movable)!=3 or len(regions)!=3:raise ValueError('Expected three pieces and graph regions')
        offset=_cycle(movable,seed);_cycle(regions,seed)
        ops.append(dict(kind='object_and_graph_region_derangement',offset=offset))
    elif task in ('iclworld_robot_07','iclworld_robot_35'):
        members=_group(spec,'blocks');factor=(.86,.91,.96)[seed%3]
        _cycle(members,seed)
        for o in members:
            o['size']=[x*factor for x in o['size']]
            o['mass']*=factor**3
        if task=='iclworld_robot_35':_update_stack_goals(spec)
        ops.append(dict(kind='new_ordered_sizes_and_layout',scale=factor,sizes={o['id']:o['size']for o in members}))
    elif task=='iclworld_robot_13':
        objects['phone']['yaw']+=math.pi/2
        objects['phone']['xy'][0]=(-.06,.06,.09)[seed%3]
        ops.append(dict(kind='phone_initial_pose',yaw=objects['phone']['yaw'],xy=objects['phone']['xy']))
    elif task=='iclworld_robot_14':
        offset=_cycle(_group(spec,'blocks'),seed,('bottom',))
        _update_stack_goals(spec)
        ops.append(dict(kind='new_tower_layer_input',offset=offset))
    elif task in ('iclworld_robot_15','iclworld_robot_16'):
        members=_group(spec,'blocks'if task=='iclworld_robot_15'else'pieces')
        _cycle(members,seed)
        for i,o in enumerate(members):o['yaw']+=((seed+i)%3+1)*math.pi/2
        if task=='iclworld_robot_16':_update_layout_transfer(spec)
        else:_update_swap_goals(spec)
        ops.append(dict(kind='new_position_orientation_input',poses={o['id']:dict(xy=o['xy'],yaw=o['yaw'])for o in members}))
    elif task=='iclworld_robot_22':
        car=objects['car'];angle=(math.pi/2,math.pi,-math.pi/2)[seed%3];car['yaw']+=angle
        _cycle(_group(spec,'blocks'),seed)
        for z in spec['zones']:
            x,y=[z['xy'][i]-car['xy'][i]for i in range(2)]
            z['xy']=[car['xy'][0]+math.cos(angle)*x-math.sin(angle)*y,
                     car['xy'][1]+math.sin(angle)*x+math.cos(angle)*y]
        ops.append(dict(kind='new_car_reference_heading_and_block_layout',heading_delta=angle))
    elif task=='iclworld_robot_26':
        cards=dict(left=1+seed%5,right=1+(seed//5)%5)
        for side,value in cards.items():
            zone=next(z for z in spec['zones']if z['id']==side+'_digit');zone['digit']=value
        sem['digit_cards']=cards;sem['execution_design_bell_rule']='paired-digit-correspondence-v3'
        ops.append(dict(kind='new_digit_pair',digits=cards))
    elif task=='iclworld_robot_30':
        cabinet=spec['mechanisms'][0]
        from .execution_design_cabinet_instances import apply_cabinet_instance
        ops.append(apply_cabinet_instance(cabinet,seed))
        # Source board_5 is 97.94mm long along body X, wider than the
        # Panda 80mm opening. Pinch its 2.742mm body-Y cross-section.
        for point in sem['handle_points'].values():point['pinch_axis_local']=[0.,1.,0.]
        # Same physical input for ABC: both are above closed and below open.
        # A/B must really close the non-target and open the target; C opens both.
        from .execution_design_drawers import SCHEMA
        values={side:(.007,.009,.011)[(seed+i)%3]for i,side in enumerate(('lower','upper'))}
        positions={sem['joint_roles'][side]['joint']:sem['joint_roles'][side]['closed']+sem['joint_roles'][side]['direction']*v for side,v in values.items()}
        cabinet['initial_joint_positions']=positions
        sem['execution_design_drawer_input']=dict(schema=SCHEMA,normalized_displacements=values)
        ops.append(dict(kind='new_initial_half_open_drawers',joint_positions=positions,normalized_displacements=values))
    elif task=='iclworld_robot_31':
        _cycle([objects['plate'],objects['bowl']],seed)
        support=objects[sem['support']]
        for z in spec['zones']:
            if z['id']=='support_center':z['xy']=deepcopy(support['xy'])
        ops.append(dict(kind='bowl_plate_position_swap'))
    elif task=='iclworld_robot_32':
        # The former far column at x=.25 placed the small cube about .903m
        # horizontally from the nearest Panda base. Its public approach
        # stalled at x=.177 before acquisition. Keep a cluttered new input,
        # but use a nearer source column; category and delivery rule stay fixed.
        # This changes only fresh I inputs (and their paired E environment).
        nearer=[]
        for name in ('sprite_bottle','cola_bottle','pink_cube'):
            obj=objects[name]
            if obj['xy'][0]>.20:
                before=deepcopy(obj['xy']);obj['xy']=[.16,-.28]
                nearer.append(dict(object=name,before=before,after=deepcopy(obj['xy'])))
        _cycle([objects[n]for n in ('sprite_bottle','cola_bottle','pink_cube')],seed)
        ops.append(dict(kind='target_instances_in_new_clutter_positions',objects=['sprite_bottle','cola_bottle','pink_cube'],nearer_source_column=nearer,native_reachability_requires_validation=True))
    elif task=='iclworld_robot_40':
        from .execution_design_clip_instances import apply_clip_instances
        ops.append(apply_clip_instances(spec,seed))
        _cycle(spec['mechanisms'],seed,('position',))
        ops.append(dict(kind='clip_instance_initial_arrangement'))
    elif task=='iclworld_robot_41':
        # New physical plank lengths, with all metric endpoint/goal metadata
        # recomputed. Rank identities alone must never hide stale geometry.
        lengths=(dict(short=.068,medium=.096,long=.132),dict(short=.072,medium=.100,long=.138),dict(short=.064,medium=.092,long=.128))[seed%3]
        for o in spec['objects']:
            rank=o['id'].split('_')[0];length=lengths[rank]
            old=o['size'][0]*2;o['size'][0]=length/2;o['mass']*=length/old
            sem['lengths'][o['id']]=length
            field='end_points'if o['id'].endswith('_ref')else'start_points'
            sem[field][o['id']][0]=(-1 if field=='end_points'else 1)*length/2
        _cycle(_group(spec,'extensions'),seed)
        zones={z['id']:z for z in spec['zones']}
        for ref,piece in sem['mapping'].items():
            r,p=objects[ref],objects[piece]
            zones[piece+'_target']['xy']=[r['xy'][0]-r['size'][0]-p['size'][0]-.001,r['xy'][1]]
        ops.append(dict(kind='new_rank_preserving_lengths',lengths=lengths))
    elif task=='iclworld_robot_43':
        # Shift launch assembly together so ball still starts supported by its
        # actual release mechanism, but the incoming line and targets change.
        dy=(-.035,.035,.055)[seed%3]
        for n in ('launcher','gate','ball'):objects[n]['xy'][1]+=dy
        # The gate is constrained to the world, so its anchor must follow the
        # actual assembly rather than pulling it back to the source Y origin.
        for joint in spec.get('joints',[]):
            if joint.get('child')=='gate' and not joint.get('parent'):
                joint['anchor0'][1]+=dy
        sem['launcher']['guide_intercept_task'][1]+=dy
        _cycle(spec['zones'],seed)
        ops.append(dict(kind='new_ball_start_and_region_layout',launch_y_shift=dy,
            assembly_joints_sha256=_hash(spec.get('joints',[]))))
    elif task=='iclworld_robot_45':
        dx=(-.065,.065,.085)[seed%3]
        for n in ['cup',*sem['groups']['balls']]:objects[n]['xy'][0]+=dx
        sem['tool_expert']['park_point_task'][0]+=dx
        ops.append(dict(kind='new_cup_and_contained_ball_start',dx=dx))
    elif task=='iclworld_robot_46':
        objects['yellow_block']['xy'][0]=(-.065,.065,.085)[seed%3]
        ops.append(dict(kind='new_cargo_initial_position',xy=objects['yellow_block']['xy']))
    else:raise NotImplementedError(task)
    return change


def apply_execution_inputs_v3(base_spec, *, condition, seed):
    task=base_spec['id']
    if task in WORKFLOW_TASKS:raise ValueError('Use the workflow builder')
    if base_spec.get('inference_generalization'):raise ValueError('Canonical source assets required, not old G1/G2')
    if base_spec.get('seed') != 0:raise ValueError('V3 input adapters require canonical source seed 0')
    contract=build_task_contract(task,base_spec['variant'],seed,condition,revision=REVISION)
    spec=deepcopy(base_spec)
    if task=='iclworld_robot_23':
        from .execution_design_robot_23_geometry import calibrate_source_branches
        calibrate_source_branches(spec)
    if task=='iclworld_robot_10':
        from .execution_design_robot_10_collision import configure_spec
        configure_spec(spec)
    if task=='iclworld_robot_43':
        from .execution_design_robot_43_geometry import calibrate_gate
        calibrate_gate(spec)
    import os
    if task=='iclworld_robot_43' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_43_ANALYTIC_BALL')=='1':
        from .execution_design_robot_43_ball import configure_spec
        configure_spec(spec)
    if task=='iclworld_robot_46' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_46_SOURCE_COOKING')=='1':
        from .execution_design_robot_46_cooking import configure_spec
        configure_spec(spec)
    if task=='iclworld_robot_37' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_37_SOURCE_SDF')=='1':
        from .execution_design_robot_37_cooking import configure_spec
        configure_spec(spec)
    if task=='iclworld_robot_28' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_28_SOURCE_SDF')=='1':
        from .execution_design_robot_28_cooking import configure_spec
        configure_spec(spec)
    if task=='iclworld_robot_18' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_18_SUPPORT')=='1':
        from .execution_design_robot_18_support import apply_support
        apply_support(spec)
    if task=='iclworld_robot_24' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_24_CLEAR_LID_LAYOUT')=='1':
        from .execution_design_robot_24_layout import apply_layout
        apply_layout(spec)
    if task=='iclworld_robot_44':
        from .execution_design_robot_44_fixture import add_passive_folding_fixture
        add_passive_folding_fixture(spec)
    if task=='iclworld_robot_47':
        from .execution_design_robot_47_fixture import add_passive_flip_fixture
        add_passive_flip_fixture(spec)
    if task in ('iclworld_robot_47','iclworld_robot_48','iclworld_robot_49','iclworld_robot_50')and os.environ.get('ICLWORLD_ENGINEERING_PRACTICAL_CARD_THICKNESS')=='1':
        from .execution_design_practical_cards import configure_spec
        configure_spec(spec)
    if task in ('iclworld_robot_47','iclworld_robot_48','iclworld_robot_49','iclworld_robot_50')and os.environ.get('ICLWORLD_ENGINEERING_PRACTICAL_CARD_SUPPORT')=='1':
        from .execution_design_practical_card_support import configure_spec
        configure_spec(spec)
    if task in ('iclworld_robot_47','iclworld_robot_48','iclworld_robot_49','iclworld_robot_50')and os.environ.get('ICLWORLD_ENGINEERING_THIN_COOKING_FIDELITY')=='1':
        from .execution_design_thin_cooking import configure_spec
        factor=os.environ.get('ICLWORLD_ENGINEERING_THIN_COLLISION_COORDINATES')
        configure_spec(spec,int(factor)if factor else None)
    if task=='iclworld_robot_45':
        from .execution_design_robot_45_acceptance_geometry import bind
        bind(spec)
    canonical_signature=physical_input_signature(spec)
    fixed=condition=='replay' or task in REPLAY_RELOCATE_TASKS
    changes=dict(kind='fixed_demo_input',semantic_seed=None)if fixed else _input(spec,seed)
    if not fixed and 26<=int(task.rsplit('_', 1)[1])<=50:
        from .execution_design_instances_v3 import apply_instance_variation
        instance_change=apply_instance_variation(spec,seed)
        if instance_change:changes['operations'].append(instance_change)
    if task=='iclworld_robot_45' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_45_ANALYTIC_BALLS')=='1':
        from .execution_design_robot_45_balls import configure_spec
        configure_spec(spec)
    if task=='iclworld_robot_46' and condition=='resample' and seed==4201:
        from .execution_design_robot_46_input_v2 import apply
        changes['operations'].append(apply(spec))
    if task=='iclworld_robot_46' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_46_EXACT_PARTITION')=='1':
        from .execution_design_robot_46_partition import configure_spec
        configure_spec(spec)
    paired_signature=physical_input_signature(spec)
    if not fixed and paired_signature==canonical_signature:
        raise ValueError(f'{task}: I must change a real input, not only metadata')
    if condition=='relocate':
        # Visual-only material: no replacement physics material, no rescaling,
        # no mirror/coordinate change, no rule-color recoloring.
        spec['table_visual']=dict(color=[.32,.43,.48],roughness=.8)
    from .execution_design_environment_v3 import environment_settings
    environment=environment_settings(task,condition)
    if environment is not None:spec['execution_environment']=environment
    spec.update(seed=seed,title=contract['title'],instruction=contract['instruction'],
                execution_design=contract['execution_design'],release_ready=False)
    spec['execution_design'].update(applied_input_changes=changes,
        paired_physical_input_sha256=paired_signature,
        environment_changes=(['table_visual','native_background_material','native_light_intensity'] if environment is not None else ['table_visual'])if condition=='relocate'else[],
        physical_acceptance_status='pending')
    if spec.get('iclworld_robot_18_support_layout'):
        from .execution_design_robot_18_support import bind_identity
        bind_identity(spec)
    if spec.get('iclworld_robot_24_lid_initial_layout'):
        from .execution_design_robot_24_layout import bind_identity
        bind_identity(spec)
    if task=='iclworld_robot_43' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_43_PASSIVE_RAIL')=='1':
        from .execution_design_robot_43_rail import configure_spec
        configure_spec(spec)
        spec['execution_design']['paired_physical_input_sha256'] = physical_input_signature(spec)
    if task == 'iclworld_robot_40' and os.environ.get('ICLWORLD_ENGINEERING_ROBOT_40_COLLISION_COORDINATES') == '1':
        from .execution_design_clip_collision_coordinates import configure_spec
        configure_spec(spec)
        spec['execution_design']['paired_physical_input_sha256'] = physical_input_signature(spec)
    if os.environ.get('ICLWORLD_ENGINEERING_THIN_CONTACT_SKIN_UM') == '50':
        from .engineering_thin_contact_skin import configure_spec
        configure_spec(spec)
        spec['execution_design']['paired_physical_input_sha256'] = physical_input_signature(spec)
    return spec


def initial_joint_positions(spec, mechanism, moving_names):
    """Validate explicit iclworld_robot_30 reset before Isaac receives any initial positions."""
    if spec.get('id')!='iclworld_robot_30' or spec.get('execution_design',{}).get('revision')!=REVISION:
        raise ValueError('Custom mechanism reset requires explicit iclworld_robot_30 v3')
    values=mechanism['initial_joint_positions'];roles=spec['semantic']['joint_roles']
    if set(values)!={r['joint']for r in roles.values()} or not set(values)<=set(moving_names):
        raise ValueError('Initial positions must name exactly the actual drawer joints')
    result={n:0. for n in moving_names}
    for side,role in roles.items():
        value=values[role['joint']]
        if type(value)not in(int,float)or not math.isfinite(value):raise ValueError('Invalid drawer reset value')
        distance=(value-role['closed'])*role['direction']
        if not 0<=distance<=spec['semantic']['joint_motion'][side]['max_travel']:
            raise ValueError('Drawer reset outside physical travel')
        result[role['joint']]=float(value)
    return result
