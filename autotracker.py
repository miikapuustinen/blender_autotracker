# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Autotrack",
    "author": "Miika Puustinen, Matti Kaihola, Stephen Leger",
    "version": (0, 0, 97),
    "blender": (2, 78, 0),
    "location": "Movie clip Editor > Tools Panel > Autotrack",
    "description": "Motion Tracking with automatic feature detection.",
    "warning": "",
    "wiki_url": "https://github.com/miikapuustinen/blender_autotracker",
    "category": "Motion Tracking",
    }

import bpy
import math
from mathutils import Vector
from bpy.types import Operator, Panel, PropertyGroup, WindowManager
from bpy.props import BoolProperty, FloatProperty, IntProperty, EnumProperty, PointerProperty

# for debug purpose
import time

class OP_Tracking_pick_frames(Operator):
    """Find longest tracks and setup frames for reconstruction"""
    bl_idname = "tracking.pick_frames"  
    bl_label = "Pick frames"
    bl_options = {"UNDO"}
    
    def find_track_start(self, track):
        for m in track.markers:
            if not m.mute:
                return m.frame
        return track.markers[0].frame
        
    def find_track_end(self, track):
        for m in reversed(track.markers):
            if not m.mute:
                return m.frame
        return track.markers[-1].frame-1
        
    def find_track_length(self, track):
        tstart = self.find_track_start(track)
        tend   = self.find_track_end(track)
        return tend-tstart
    """
        find the 12 longest tracks start and end
    """
    def pick_keyframes(self, context):
        scene = context.scene
        clip = context.area.spaces.active.clip
        tracking = clip.tracking
        tracks = tracking.tracks
        longest_tracks = []
        tracks_list  = [track for track in tracks]
        track_length = [self.find_track_length(track) for track in tracks]
        for i in range(12):
            index = track_length.index(max(track_length))    
            longest_tracks.append(tracks_list[index])
            tracks_list.pop(index)
            track_length.pop(index)
        tracks_start = [self.find_track_start(track) for track in longest_tracks]
        tracks_end   = [self.find_track_end(track) for track in longest_tracks]
        tracks_end.append(scene.frame_end-1)
        tracks_start.append(scene.frame_start+1)
        keyframe_a = max(tracks_start)
        keyframe_b = min(tracks_end)
        delta = keyframe_b-keyframe_a
        if delta > 20:
            keyframe_a += int(delta / 4)
            keyframe_b -= int(delta / 4)
        tracking.objects[0].keyframe_a = keyframe_a
        tracking.objects[0].keyframe_b = keyframe_b
        tracking.settings.use_keyframe_selection = False
        print("pick_keyframes %s - %s" % (keyframe_a,keyframe_b))
    @classmethod
    def poll(cls, context):
        return (context.area.spaces.active.clip is not None)
        
    def execute(self, context):
        clip = context.area.spaces.active.clip
        try:
            tracking = clip.tracking
            tracks = tracking.tracks
            start = tracking.reconstruction.cameras[0].frame
            end   = tracking.reconstruction.cameras[-1].frame
        except:
            return {'CANCELED'}
        self.pick_keyframes(context)
        return {'FINISHED'}

class OP_Tracking_refine_solution(Operator):
    """Set track weight by error and solve camera motion"""
    bl_idname = "tracking.refine_solution"  
    bl_label = "Refine"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return (context.area.spaces.active.clip is not None)
        
    def execute(self, context):
        error = context.window_manager.TrackingTargetError
        smooth = context.window_manager.TrackingSmooth
        clip = context.area.spaces.active.clip
        try:
            tracking = clip.tracking
            tracks = tracking.tracks
            winx = float(clip.size[0])
            winy = float(clip.size[1])
            aspy =  1.0 / tracking.camera.pixel_aspect
            start = tracking.reconstruction.cameras[0].frame
            end   = tracking.reconstruction.cameras[-1].frame
        except:
            return {'CANCELED'}
        
        marker_position = Vector()
        
        for frame in range(start, end):
            camera = tracking.reconstruction.cameras.find_frame(frame)
            if camera is not None:
                imat = camera.matrix.inverted()
                projection_matrix = imat.transposed()
            else:
                continue
            
            for track in tracking.tracks:
                marker = track.markers.find_frame(frame)
                if marker is None:
                    continue
                    
                # weight incomplete tracks on start and end
                if frame > start + smooth and frame < end - smooth:
                    for m in track.markers:
                        if not m.mute:
                            tstart = m.frame
                            break
                    for m in reversed(track.markers):
                        if not m.mute:
                            tend = m.frame
                            break
                    dt = min(0.5 * (tend - tstart), smooth)
                    if dt > 0:
                        t0 = min(1.0, (frame - tstart) / dt)
                        t1 = min(1.0, (tend - frame) / dt)
                        tw = min(t0, t1)
                    else:
                        tw = 0.0
                else:
                    tw = 1.0
                    
                reprojected_position = track.bundle * projection_matrix
                if reprojected_position.z == 0:
                    track.weight = 0
                    track.keyframe_insert("weight", frame=frame)
                    continue
                reprojected_position = reprojected_position / -reprojected_position.z * tracking.camera.focal_length_pixels
                reprojected_position = Vector((tracking.camera.principal[0] + reprojected_position[0],tracking.camera.principal[1] * aspy + reprojected_position[1], 0))
                
                marker_position[0] = (marker.co[0] + track.offset[0]) * winx
                marker_position[1] = (marker.co[1] + track.offset[1]) * winy * aspy
                
                dp = marker_position - reprojected_position
                if dp.length == 0:
                    track.weight = 1.0
                else:
                    track.weight = min(1.0, tw * error / dp.length)
                track.keyframe_insert("weight", frame=frame)
            
            
        bpy.ops.clip.solve_camera()
        return{'FINISHED'}
        
class OP_Tracking_reset_solution(Operator):
    """Reset track weight and solve camera motion"""
    bl_idname = "tracking.reset_solution"  
    bl_label = "Reset"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return (context.area.spaces.active.clip is not None)
    
    def execute(self, context):
        clip = context.area.spaces.active.clip
        try:
            tracking = clip.tracking
            tracks = tracking.tracks
            start = tracking.reconstruction.cameras[0].frame
            end   = tracking.reconstruction.cameras[-1].frame
        except:
            return {'CANCELED'}
        for frame in range(start, end):
            camera = tracking.reconstruction.cameras.find_frame(frame)
            if camera is None:
                continue
            for track in tracking.tracks:
                marker = track.markers.find_frame(frame)
                if marker is None:
                    continue
                track.weight = 1.0
                track.keyframe_insert("weight", frame=frame)       
        bpy.ops.clip.solve_camera()
        return{'FINISHED'}

class OP_Tracking_auto_tracker(Operator):
    """Autotrack. Esc to cancel."""
    bl_idname = "tracking.auto_track"
    bl_label = "AutoTracking"

    limits = IntProperty(default=0)
    _timer = None
    
    # DETECT FEATURES
    def auto_features(self, context):
        t = time.time()
        scene = context.scene
        props = context.window_manager.autotracker_props
        clip  = context.area.spaces.active.clip
        width = clip.size[0]
        delete_threshold = props.delete_threshold/100.0
        
        selected = []
        old = []
        to_delete = []

        bpy.ops.clip.select_all(action='DESELECT')

        # Detect Features
        bpy.ops.clip.detect_features(
            threshold=props.df_threshold,
            min_distance=props.df_distance/100.0*width,
            margin=props.df_margin/100.0*width,
            placement=props.placement_list
            )

        current_frame = scene.frame_current

        tracks = clip.tracking.tracks
        for track in tracks:
            marker = track.markers.find_frame(current_frame)
            if marker is not None:
                if (not track.select) and (not track.hide) and (not marker.mute):
                    old.append(track)
                if track.select:
                    selected.append(track)
            
        # Select overlapping new markers
        for track_new in selected:
            marker0 = track_new.markers.find_frame(current_frame)
            for track_old in old:
                marker1 = track_old.markers.find_frame(current_frame)
                distance = (marker1.co-marker0.co).length
                if distance < delete_threshold:
                    to_delete.append(track_new)
                    break
            
        # delete short tracks
        for track in tracks:
            
            muted  = []
            active = []
            # print(track)
            for marker in track.markers:
                if marker.mute:
                    muted.append(marker)
                else:
                    active.append(marker)
            if len(muted) > 3 and len(active) < props.small_tracks:
                to_delete.append(track)

            if len(track.markers) > 1 and len(active) == 0:
                to_delete.append(track)
        
        # Delete Overlapping Markers
        bpy.ops.clip.select_all(action='DESELECT')
        for track in tracks:
            if track in to_delete:
                track.select = True
        bpy.ops.clip.delete_track()
        print("auto_features %.4f seconds %s / %s tracks tracking." % (time.time()-t, len(selected), len(tracks)))
    
    # AUTOTRACK FRAMES
    def track_frames_backward(self):
        bpy.ops.clip.track_markers(backwards=True, sequence=False)


    def track_frames_forward(self):
        bpy.ops.clip.track_markers(backwards=False, sequence=False)
        
    """
        compute mean pixel motion for current frame
    """
    def estimate_motion(self, context):
        t = time.time()
        scene = context.scene
        props = context.window_manager.autotracker_props
        clip  = context.area.spaces.active.clip
        tracks = clip.tracking.tracks
        current_frame = scene.frame_current

        if props.track_backwards:
            last_frame = current_frame+1
        else:
            last_frame = current_frame-1
        nbtracks = 0
        distance = 0.0
        for track in tracks:
            marker0 = track.markers.find_frame(current_frame)
            marker1 = track.markers.find_frame(last_frame)
            if marker0 is not None and marker1 is not None:
                d = (marker0.co-marker1.co).length
                # skip fixed tracks
                if d > 0:
                    distance += d
                    nbtracks += 1
                
        if nbtracks > 0:
            mean = distance / nbtracks
        else:
            # arbitrary set to prevent division by 0 error
            mean = 10
        print("estimate_motion :%.4f seconds markers:%s total:%.4f mean:%.4f" % (time.time()-t, nbtracks, distance, mean))
        return mean
            
    # REMOVE BAD MARKERS
    def remove_extra(self, context):
        t = time.time()
        scene = context.scene
        props = context.window_manager.autotracker_props
        clip  = context.area.spaces.active.clip
        
        # mean motion (normalized [0-1]) distance for tracks between last and current frame
        mean = self.estimate_motion(context)
        
        # how much a track is allowed to move 
        allowed = mean * props.jump_cut
        
        tracks = clip.tracking.tracks
        current_frame = scene.frame_current
        
        if props.track_backwards:
            last_frame = current_frame+1
        else:
            last_frame = current_frame-1

        for track in tracks:
            marker0 = track.markers.find_frame(current_frame)
            marker1 = track.markers.find_frame(last_frame)
            if marker0 is not None and marker1 is not None:
                distance = (marker0.co-marker1.co).length
                # Jump Cut threshold
                if distance > allowed:
                    """
                    if (i.markers.find_frame(current_frame) is not None and
                       i.markers.find_frame(current_frame - one_frame) is not None):
                    """
                    # create new track to new pos
                    new_track = \
                        clip.tracking.tracks.new(frame=current_frame)
                    new_track.markers[0].co = marker0.co
                    marker0.mute = True
        print("remove_extra :%.4f seconds" % (time.time()-t))  
    
    def modal(self, context, event):
        
        # prevent TIMER event while running
        self.cancel(context)
            
        if event.type in {'ESC'}:
            self.limits = 0
            print("Cancelling")
            return {'FINISHED'}
        
        scene = context.scene
        props = context.window_manager.autotracker_props
        clip  = context.area.spaces.active.clip
            
        if (scene.frame_current == scene.frame_end + 1 or
            scene.frame_current == scene.frame_start - 1):
            self.limits = 0
            print("Reached scene end, now solving if enabled")
            if props.auto_solve:
                # pick keyframes from longest tracks as reconstruction basis
                t = time.time()
                bpy.ops.tracking.pick_frames()
                print("pick_frames :%.2f seconds" % (time.time()-t)) 
                # first solve as usual
                t = time.time()
                bpy.ops.tracking.reset_solution()
                print("reset_solution :%.2f seconds" % (time.time()-t)) 
                # then refine
                if props.auto_refine:
                    t = time.time()
                    bpy.ops.tracking.refine_solution()
                    print("refine_solution :%.2f seconds" % (time.time()-t)) 
            return {'FINISHED'}
            
        print("Tracking frame %s" % (scene.frame_current))
        
        if scene.frame_current % props.frame_separation == 0 or self.limits == 0:
            self.auto_features(context)

        # Select all trackers for tracking
        bpy.ops.clip.select_all(action='SELECT')
        tracks = clip.tracking.tracks
        active_tracks = []

        # Don't track locked or hidden tracks
        for track in tracks:
            if track.lock:
                track.select = False
            else:
                active_tracks.append(track)

        # Forwards or backwards tracking
        
        if len(active_tracks) == 0:
            print("No new tracks created. Doing nothing.")
            self.limits = 0
            self.cancel(context)
            return {'FINISHED'}
            
        if props.track_backwards:
            self.track_frames_backward()
        else:
            self.track_frames_forward()

        # Remove bad tracks
        if self.limits >= 3:
            self.remove_extra(context)
            
        self.limits += 1
        
        # setup a timer to broadcast a TIMER event to force modal to re-run as fast as possible (not waiting for any mouse or keyboard event) 
        self._timer = context.window_manager.event_timer_add(time_step=0.001, window=context.window)
        
        #return {'PASS_THROUGH'}
        
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
        
class AutotrackerSettings(PropertyGroup):
    """Create properties"""
    df_margin = FloatProperty(
            name="Detect Features Margin",
            description="Only features further margin pixels from the image edges are considered.",
            subtype='PERCENTAGE',
            default=5,
            min=0,
            max=100
            )
            
    df_threshold = FloatProperty(
            name="Detect Features Threshold",
            description="Threshold level to concider feature good enough for tracking.",
            default=0.3,
            min=0.0,
            max=1.0
            )
    # Note: merge this one with delete_threshold        
    df_distance = FloatProperty(
            name="Detect Features Distance",
            description="Minimal distance accepted between two features.",
            subtype='PERCENTAGE',
            default=8,
            min=1,
            max=100
            )

    delete_threshold = FloatProperty(
            name="New Marker Threshold",
            description="Threshold how near new features can appear during autotracking.",
            subtype='PERCENTAGE',
            default=8,
            min=1,
            max=100
            )
            
    small_tracks = IntProperty(
            name="Minimum track length",
            description="Delete tracks shortest than this number of frames.",
            default=50,
            min=1,
            max=1000
            )
            
    frame_separation = IntProperty(
            name="Frame Separation",
            description="How often new features are generated.",
            default=5,
            min=1,
            max=100
            )

    jump_cut = FloatProperty(
            name="Jump Cut",
            description="Distance how much a marker can travel before it is considered "
                        "to be a bad track and cut. A new track is added. (factor relative to mean motion)",
            default=5.0,
            min=0.0,
            max=50.0
            )

    track_backwards = BoolProperty(
            name="AutoTrack Backwards",
            description="Autotrack backwards.",
            default=False
            )

    # Dropdown menu
    list_items = [
        ("FRAME", "Whole Frame", "", 1),
        ("INSIDE_GPENCIL", "Inside Grease Pencil", "", 2),
        ("OUTSIDE_GPENCIL", "Outside Grease Pencil", "", 3),
    ]

    placement_list = EnumProperty(
            name="",
            description="Feature Placement",
            items=list_items
            )
    
    auto_solve = BoolProperty(
            name = "Solve",
            description="Automatically solve after tracking",
            default=True
            )
    
    auto_refine = BoolProperty(
            name = "Refine",
            description="Automatically refine after solving",
            default=True
            )
# UI CREATION #
class AutotrackerPanel(Panel):
    """Creates a Panel in the Render Layer properties window"""
    bl_label = "Autotrack"
    bl_idname = "autotrack"
    bl_space_type = 'CLIP_EDITOR'
    bl_region_type = 'TOOLS'
    bl_category = "Track"

    # Draw UI
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        row = layout.row(align=True)
        row.scale_y = 1.5

        props = row.operator("tracking.auto_track", text="Autotrack!     ", icon='PLAY')

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "track_backwards")

        row = layout.row(align=True)  # make next row
        row.prop(wm.autotracker_props, "delete_threshold")
        
        row = layout.row(align=True)  # make next row
        row.prop(wm.autotracker_props, "small_tracks")

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "frame_separation", text="Frame Separation")

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "jump_cut", text="Jump Threshold")

        row = layout.row(align=True)
        row.label(text="Detect Features Settings:")

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "df_margin", text="Margin:")

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "df_threshold", text="Threshold:")

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "df_distance", text="Distance:")

        row = layout.row(align=True)
        row.label(text="Feature Placement:")

        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "placement_list")
            
        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "auto_solve")
        
        row = layout.row(align=True)
        row.prop(wm.autotracker_props, "auto_refine")

"""
    NOTE:
    All size properties are in percent of clip size, so presets does not depends on clip size
"""
class RefineMotionTrackingPanel(Panel):
    bl_label = "Refine solution"
    bl_space_type = "CLIP_EDITOR"
    bl_region_type = "TOOLS"
    bl_category = "Solve"
    
    @classmethod
    def poll(cls, context):
        return (context.area.spaces.active.clip is not None) 
    
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row(align=True)
        row.label("Refine")
        row = box.row(align=True)
        row.prop(context.window_manager, "TrackingTargetError", text="Target error")
        row = box.row(align=True)
        row.prop(context.window_manager, "TrackingSmooth", text="Smooth transition")
        row = box.row(align=True)
        row.operator("tracking.refine_solution")
        row.operator("tracking.reset_solution")

                       
# REGISTER BLOCK #
def register():
    bpy.utils.register_class(AutotrackerSettings)
    WindowManager.TrackingTargetError = FloatProperty(
        name="error", 
        description="Refine motion track target error", 
        default=0.3, 
        min=0.01)
    WindowManager.TrackingSmooth = FloatProperty(
        name="Smooth transition", 
        description="Smooth weight transition on start and end of incomplete tracks", 
        default=25, 
        min=1)
    WindowManager.autotracker_props = \
        PointerProperty(type=AutotrackerSettings)
    bpy.utils.register_module(__name__)  
    

def unregister():
    bpy.utils.unregister_class(AutotrackerSettings)
    bpy.utils.unregister_module(__name__)   
    del WindowManager.TrackingTargetError
    del WindowManager.TrackingSmooth
    del WindowManager.autotracker_props

if __name__ == "__main__":
    register()
