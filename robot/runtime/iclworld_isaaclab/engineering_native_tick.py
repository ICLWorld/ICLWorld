"""Route private native primitives through an exclusive engineering RoomPool.

The controller remains attached to its pool. The original shared-world
write/step/read/hooks path is used once for every requested physical tick.
"""
from contextlib import contextmanager


@contextmanager
def diagnostic_tick_scope(author,*,reference_authorization=False):
    c=author.c;pool=getattr(c,'_room_pool',None)
    source_reference=False
    if reference_authorization:
        spec=getattr(getattr(author,'scene',None),'spec',{})
        design=spec.get('execution_design',{})
        common=(spec.get('seed')==4201
            and design.get('revision')=='embodied50-execution-v3-20261102')
        source_reference=common and(
            (getattr(author,'_engineering_robot_37_verified_path',False)is True
             and spec.get('id')=='iclworld_robot_37'and design.get('condition')=='replay')or
            (getattr(author,'_engineering_robot_31_verified_path',False)is True
             and spec.get('id')=='iclworld_robot_31'and spec.get('variant')=='C'
             and design.get('condition')=='resample')or
            (getattr(author,'_engineering_robot_28_contact_hold',False)is True
             and spec.get('id')=='iclworld_robot_28'and design.get('condition')=='resample'))
        if not source_reference:
            raise ValueError('Explicit isolated task reference primitive authorization required')
    if not author.control_report.get('engineering_reference_only')or not(
            getattr(c,'_engineering_diagnostic_only',False)or source_reference):
        raise ValueError('Exclusive native tick bridge requires an admitted engineering diagnostic or isolated task reference')
    if pool is None:
        yield
        return
    rooms=[room for room,controller in pool.controllers.items()if controller is c]
    if len(pool.controllers)!=1 or len(rooms)!=1 or rooms[0]in pool.terminal:
        raise ValueError('Native tick bridge requires one live diagnostic room and no sibling controller')
    if getattr(c,'_engineering_tick_bridge_active',False):raise ValueError('Nested native tick bridges are forbidden')
    previous=c.tick;had_override='tick'in vars(c);active=[False]
    def tick(render=False,*,phase='full'):
        if phase!='full':return previous(render=render,phase=phase)
        if active[0]:raise RuntimeError('Recursive full shared-world tick')
        active[0]=True
        try:return pool.tick(render=render)
        finally:active[0]=False
    c._engineering_tick_bridge_active=True;c.tick=tick
    try:yield
    finally:
        if had_override:c.tick=previous
        else:del c.tick
        c._engineering_tick_bridge_active=False
