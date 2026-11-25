"""Front25 local segments use the shared engineering checkpoint gate."""
import importlib

MODULES={
    'iclworld_robot_15':'execution_design_segments_robot_15',
    'iclworld_robot_18':'execution_design_segments_robot_18',
    'iclworld_robot_17':'execution_design_segments_robot_17_robot_20','iclworld_robot_20':'execution_design_segments_robot_17_robot_20',
    'iclworld_robot_19':'execution_design_segments_robot_19_robot_25','iclworld_robot_25':'execution_design_segments_robot_19_robot_25',
    'iclworld_robot_23':'execution_design_segments_robot_23_robot_24','iclworld_robot_24':'execution_design_segments_robot_23_robot_24',
}


iclworld_robot_20_ENTRIES={'iclworld_robot_20_grasp_blue','iclworld_robot_20_grasp_and_lift_blue','iclworld_robot_20_b_grasp_and_lift_blue1','iclworld_robot_20_liftoff_red','iclworld_robot_20_c_place_next_blue_from423'}
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_b_reseat_lift_blue_from2')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_a_grasp_lift_blue_from268')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_c_finish_blue_transfer_from321')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_c_reacquire_supported_blue_from1')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_a_lift_red_from543')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_a_finish_after_red_lift7')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_b_pickup_blue_left_from424')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_b_lift_and_finish_from_left98')
iclworld_robot_20_ENTRIES.add('iclworld_robot_20_c_direct_remaining_from423')

iclworld_robot_17_EXTRA_MODULES={
    'iclworld_robot_17_a_edge_grip_floor_after1':'execution_design_segments_robot_17_a_remaining',
    'iclworld_robot_17_c_edge_grip_remaining90':'execution_design_robot_17_two_blue_remaining',
    'iclworld_robot_17_c_low_ingress_from_held100':'execution_design_robot_17_two_blue_remaining',
    'iclworld_robot_17_c_low_ingress_from_held2':'execution_design_robot_17_two_blue_remaining',
    'iclworld_robot_17_b_handover_recycle_from_held187':'execution_design_robot_17_recycle_delivery',
}

def solve(author,checkpoint,request):
    task=author.scene.spec['id'];entry=request['entry']
    if task not in MODULES or not entry.startswith(task.lower()+'_'):
        raise ValueError('Explicit registered front25 local segment required')
    if task=='iclworld_robot_20' and entry not in iclworld_robot_20_ENTRIES:
        raise ValueError('Explicit registered iclworld_robot_20 local segment required')
    if task=='iclworld_robot_17' and entry in iclworld_robot_17_EXTRA_MODULES and (checkpoint.get('diagnostic_only')is not True or not author.control_report.get('engineering_reference_only')or not getattr(author.c,'_engineering_diagnostic_only',False)or not getattr(author.c,'_engineering_checkpoint_readback_passed',False)):
        raise ValueError('Short segment requires admitted native checkpoint restoration/readback')
    if entry in('iclworld_robot_17_a_floor_regrasp_green_99','iclworld_robot_17_a_floor_regrasp_after_close7','iclworld_robot_17_a_continue_actual_push22','iclworld_robot_17_a_box_axis_grasp_floor33') and (checkpoint.get('diagnostic_only')is not True or not author.control_report.get('engineering_reference_only')or not getattr(author.c,'_engineering_diagnostic_only',False)or not getattr(author.c,'_engineering_checkpoint_readback_passed',False)):
        raise ValueError('Short segment requires admitted native checkpoint restoration/readback')
    if entry in('iclworld_robot_17_b_recycle_low_from_held999','iclworld_robot_17_b_recycle_deliver_after_release16','iclworld_robot_17_c_release_in_region_blue_117','iclworld_robot_17_c_resume_after_two_blues_1','iclworld_robot_17_c_resume_before_sweep11') and (checkpoint.get('diagnostic_only')is not True or not author.control_report.get('engineering_reference_only')or not getattr(author.c,'_engineering_diagnostic_only',False)or not getattr(author.c,'_engineering_checkpoint_readback_passed',False)):
        raise ValueError('Short segment requires admitted native checkpoint restoration/readback')
    if entry in ('iclworld_robot_17_a_finish_from_actual_held40','iclworld_robot_17_b_release_actual_upper_green_492','iclworld_robot_17_c_place_actual_held_blue_336','iclworld_robot_17_a_regrasp_after_lost_green_1','iclworld_robot_17_c_resume_remaining_above_rail_121','iclworld_robot_20_grasp_and_lift_blue','iclworld_robot_20_b_grasp_and_lift_blue1','iclworld_robot_20_c_place_next_blue_from423','iclworld_robot_17_b_resume_held_upper_triangle_848','iclworld_robot_17_b_place_held_upper_from_hover_722','iclworld_robot_17_a_release_box_nudge_regrasp_223','iclworld_robot_17_c_confirm_released_upper_blue_222','iclworld_robot_17_a_grasp_green_floor_edge_57','iclworld_robot_17_a_grasp_green_base_18','iclworld_robot_17_c_resume_remaining_after_blue_release_1','iclworld_robot_17_c_resume_remaining_after_relevel_93','iclworld_robot_17_a_resume_held_green_and_remaining_37','iclworld_robot_17_b_resume_remaining_after_upper_213'):
        if (checkpoint.get('diagnostic_only')is not True
                or not author.control_report.get('engineering_reference_only')
                or not getattr(author.c,'_engineering_diagnostic_only',False)
                or not getattr(author.c,'_engineering_checkpoint_readback_passed',False)):
            raise ValueError('Short segment requires admitted native checkpoint restoration/readback')
    module_name=MODULES[task]
    if task=='iclworld_robot_17' and entry in iclworld_robot_17_EXTRA_MODULES:
        module_name=iclworld_robot_17_EXTRA_MODULES[entry]
    elif task=='iclworld_robot_20' and entry=='iclworld_robot_20_c_place_next_blue_from423':
        module_name='execution_design_robot_20_slots'
    elif task=='iclworld_robot_18' and entry in ('iclworld_robot_18_grasp_lift_ball_from616','iclworld_robot_18_grasp_lift_ball_from_open483'):
        module_name='execution_design_robot_18_ball'
    elif task=='iclworld_robot_18' and entry=='iclworld_robot_18_contact_offsets_from102':
        module_name='execution_design_robot_18_contact_read'
    elif task=='iclworld_robot_18' and entry=='iclworld_robot_18_closed_cap_from3':
        module_name='execution_design_robot_18_closed_cap'
    elif task=='iclworld_robot_18' and entry in ('iclworld_robot_18_roll_selected_ball_from160','iclworld_robot_18_roll_selected_ball_from_closed3','iclworld_robot_18_roll_selected_ball_from_tilted40'):
        module_name='execution_design_robot_18_ball_roll'
    elif task=='iclworld_robot_20' and entry=='iclworld_robot_20_b_reseat_lift_blue_from2':
        module_name='execution_design_robot_20_b_reseat'
    elif task=='iclworld_robot_20' and entry=='iclworld_robot_20_b_pickup_blue_left_from424':
        module_name='execution_design_robot_20_b_direct_left'
    elif task=='iclworld_robot_20' and entry=='iclworld_robot_20_b_lift_and_finish_from_left98':
        module_name='execution_design_robot_20_b_held98'
    elif task=='iclworld_robot_20' and entry=='iclworld_robot_20_c_direct_remaining_from423':
        module_name='execution_design_robot_20_c_direct_remaining'
    elif task=='iclworld_robot_20' and entry=='iclworld_robot_20_a_grasp_lift_blue_from268':
        module_name='execution_design_robot_20_a_grip'
    elif task=='iclworld_robot_20' and entry in('iclworld_robot_20_a_lift_red_from543','iclworld_robot_20_a_finish_after_red_lift7'):
        module_name='execution_design_robot_20_a_red'
    elif task=='iclworld_robot_20' and entry in('iclworld_robot_20_c_finish_blue_transfer_from321','iclworld_robot_20_c_reacquire_supported_blue_from1'):
        module_name='execution_design_robot_20_c_transfer'
    elif task=='iclworld_robot_25' and entry=='iclworld_robot_25_a_release_spoon_from600':
        module_name='execution_design_robot_25_a_spoon_release'
    elif task=='iclworld_robot_17' and entry in ('iclworld_robot_17_a_resume_after_lower_first','iclworld_robot_17_b_resume_after_lower_first'):
        module_name='execution_design_segments_robot_17'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_a_release_box_nudge_regrasp_223':
        module_name='execution_design_segments_robot_17_regrasp'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_a_grasp_green_floor_edge_57','iclworld_robot_17_a_grasp_green_base_18'):
        module_name='execution_design_segments_robot_17_regrasp_edge'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_a_floor_regrasp_green_99','iclworld_robot_17_a_floor_regrasp_after_close7','iclworld_robot_17_a_continue_actual_push22','iclworld_robot_17_a_box_axis_grasp_floor33'):
        module_name='execution_design_robot_17_a_floor_regrasp'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_b_recycle_deliver_after_release16':
        module_name='execution_design_robot_17_complete_layers'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_b_recycle_low_from_held999':
        module_name='execution_design_robot_17_recycle_delivery'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_c_release_in_region_blue_117':
        module_name='execution_design_robot_17_release_current'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_c_resume_after_two_blues_1','iclworld_robot_17_c_resume_before_sweep11'):
        module_name='execution_design_robot_17_two_blue_remaining'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_b_release_actual_upper_green_492','iclworld_robot_17_c_place_actual_held_blue_336'):
        module_name='execution_design_robot_17_actual_upper'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_b_resume_remaining_after_upper_213':
        module_name='execution_design_segments_robot_17_b_remaining'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_a_resume_held_green_and_remaining_37','iclworld_robot_17_a_regrasp_after_lost_green_1','iclworld_robot_17_a_finish_from_actual_held40'):
        module_name='execution_design_segments_robot_17_a_remaining'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_b_resume_held_upper_triangle_848','iclworld_robot_17_b_place_held_upper_from_hover_722'):
        module_name='execution_design_segments_robot_17_held_upper'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_c_place_held_blue_upper_south':
        module_name='execution_design_segments_robot_17_upper'
    elif task=='iclworld_robot_17' and entry=='iclworld_robot_17_c_confirm_released_upper_blue_222':
        module_name='execution_design_segments_robot_17_completion'
    elif task=='iclworld_robot_17' and entry in('iclworld_robot_17_c_resume_remaining_after_blue_release_1','iclworld_robot_17_c_resume_remaining_after_relevel_93','iclworld_robot_17_c_resume_remaining_above_rail_121'):
        module_name='execution_design_segments_robot_17_remaining'
    module=importlib.import_module('.'+module_name,__package__)
    previous=getattr(author,'_execution_design_reference_authorized',False)
    author._execution_design_reference_authorized=True
    try:result=module.run_segment(author,entry,request['parameters'])
    finally:author._execution_design_reference_authorized=previous
    if any(k in result for k in ('success','strict_success','task_score_100')):
        raise ValueError('Local segment must not supply a full-task grade')
    return dict(result,segment_passed=result.get('local_completed')is True,
                full_task_acceptance=False)
