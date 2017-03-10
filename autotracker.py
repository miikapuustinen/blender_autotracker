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
import bgl
import blf
import math
from mathutils import Vector
from bpy.types import Operator, Panel, PropertyGroup, WindowManager
from bpy.props import BoolProperty, FloatProperty, IntProperty, EnumProperty, PointerProperty

# for debug purpose
import time


# http://blenderscripting.blogspot.ch/2011/07/bgl-drawing-with-opengl-onto-blender-25.html
class GlDrawOnScreen():
    black = (0.0, 0.0, 0.0, 0.7)
    white = (1.0, 1.0, 1.0, 0.5)
    progress_colour = (0.2, 0.7, 0.2, 0.5)
    def String(self, text, x, y, size, colour):
        ''' my_string : the text we want to print
            pos_x, pos_y : coordinates in integer values
            size : font height.
            colour : used for definining the colour'''
        dpi, font_id = 72, 0 # dirty fast assignment
        bgl.glColor4f(*colour)
        blf.position(font_id, x, y, 0)
        blf.size(font_id, size, dpi)
        blf.draw(font_id, text)
    def _end(self):
        bgl.glEnd()
        bgl.glPopAttrib()
        bgl.glLineWidth(1)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    def _start_line(self, colour, width=2, style=bgl.GL_LINE_STIPPLE):
        bgl.glPushAttrib(bgl.GL_ENABLE_BIT)
        bgl.glLineStipple(1, 0x9999)
        bgl.glEnable(style)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glColor4f(*colour)
        bgl.glLineWidth(width)
        bgl.glBegin(bgl.GL_LINE_STRIP)
    def Rectangle(self, x0, y0, x1, y1, colour, width=2, style=bgl.GL_LINE):
        self._start_line(colour, width, style) 
        bgl.glVertex2i(x0, y0)
        bgl.glVertex2i(x1, y0)
        bgl.glVertex2i(x1, y1)
        bgl.glVertex2i(x0, y1)
        bgl.glVertex2i(x0, y0)
        self._end()
    def Polygon(self, pts, colour):
        bgl.glPushAttrib(bgl.GL_ENABLE_BIT)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glColor4f(*colour)    
        bgl.glBegin(bgl.GL_POLYGON)
        for pt in pts:
            x, y = pt
            bgl.glVertex2f(x, y)  
        self._end()
    def ProgressBar(self, x, y, width, height, start, percent):
        x1, y1 = x+width, y+height
        # progress from current point to either start or end
        xs = x+(x1-x) * float(start)
        if percent > 0:
            # going forward
            xi = xs+(x1-xs) * float(percent)
        else:
            # going backward
            xi = xs-(x-xs) * float(percent)
        self.Polygon([(xs, y), (xs, y1), (xi, y1), (xi, y)], self.progress_colour)
        self.Rectangle(x, y, x1, y1, self.white, width=1)
        
def draw_callback(self, context):
    print("draw_callback : %s" % (self.progress))
    self.gl.ProgressBar(10, 24, 200, 16, self.start, self.progress)
    self.gl.String(str(int(100*abs(self.progress)))+"%", 14, 28, 10, self.gl.white)
    
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
        tracking.objects.active.keyframe_a = keyframe_a
        tracking.objects.active.keyframe_b = keyframe_b
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
        print("Solve error %.2f" % (tracking.reconstruction.average_error))
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
        print("Solve error %.2f" % (tracking.reconstruction.average_error))
        return{'FINISHED'}

class OP_Tracking_auto_tracker(Operator):
    """Autotrack. Esc to cancel."""
    bl_idname = "tracking.auto_track"
    bl_label = "AutoTracking"

    _timer = None
    _draw_handler = None
    
    gl = GlDrawOnScreen()
    progress = 0
    limits = 0
    t = 0
    
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
    
    def show_tracks(self, context):
        scene = context.scene
        clip  = context.area.spaces.active.clip
        tracks = clip.tracking.tracks
        for track in tracks:
            track.hide = False
        
    def get_vars_from_context(self, context):    
        scene = context.scene
        props = context.window_manager.autotracker_props
        clip  = context.area.spaces.active.clip
        tracks = clip.tracking.tracks
        current_frame = scene.frame_current
        if props.track_backwards:
            last_frame = current_frame+props.frame_separation
        else:
            last_frame = current_frame-props.frame_separation
        return scene, props, clip, tracks, current_frame, last_frame
    
    def delete_tracks(self, to_delete):
        bpy.ops.clip.select_all(action='DESELECT')
        for track in to_delete:
            track.select = True
        bpy.ops.clip.delete_track()
        
    
    # DETECT FEATURES
    def auto_features(self, context):
        t = time.time()
        
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        
        selected = []
        old = []
        to_delete = []
        width = clip.size[0]
        delete_threshold = float(props.delete_threshold)/100.0
        
        bpy.ops.clip.select_all(action='DESELECT')
        
        # Detect Features
        bpy.ops.clip.detect_features(
            threshold=props.df_threshold,
            min_distance=props.df_distance/100.0*width,
            margin=props.df_margin/100.0*width,
            placement=props.placement_list
            )
            
        # filter new and old tracks
        for track in tracks:
            if track.hide or track.lock:
                continue
            marker = track.markers.find_frame(current_frame)
            if marker is not None:
                if (not track.select) and (not marker.mute):
                    old.append(track)
                if track.select:
                    selected.append(track)
        
        added_tracks = len(selected)
        
        # Select overlapping new markers
        for track_new in selected:
            marker0 = track_new.markers.find_frame(current_frame)
            for track_old in old:
                marker1 = track_old.markers.find_frame(current_frame)
                distance = (marker1.co-marker0.co).length
                if distance < delete_threshold:
                    to_delete.append(track_new)
                    added_tracks -= 1
                    break
        
        # Delete Overlapping Markers
        self.delete_tracks(to_delete)
        print("auto_features %.4f seconds add:%s tracks." % (time.time()-t, added_tracks))
    
    
    # AUTOTRACK FRAMES
    def track_frames_backward(self):
        t = time.time()
        bpy.ops.clip.track_markers(backwards=True, sequence=True)
        print("track_frames_backward %.2f seconds" % (time.time()-t))
    
    def track_frames_forward(self):
        t = time.time()
        bpy.ops.clip.track_markers(backwards=False, sequence=True)
        print("track_frames_forward %.2f seconds" % (time.time()-t))
    
    def select_active_tracks(self, context):
        t = time.time()
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        # Select active trackers for tracking
        bpy.ops.clip.select_all(action='DESELECT')
        selected = []
        for track in tracks:
            if track.hide or track.lock:
                continue
            if len(track.markers) < 2:
                track.select = True
            else:
                marker = track.markers.find_frame(current_frame)
                track.select = (marker is not None) and (not marker.mute)
            if track.select:
                selected.append(track)
                
        print("select_active_tracks %.2f seconds selected:%s" % (time.time()-t, len(selected)))
        return selected
        
    """
        compute mean pixel motion for current frame
        TODO: use statistic here to make filtering more efficient
    """
    def estimate_motion(self, context, last, frame):
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        nbtracks = 0
        distance = 0.0
        for track in tracks:
            if track.hide or track.lock:
                continue
            marker0 = track.markers.find_frame(frame)
            marker1 = track.markers.find_frame(last)
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
        
        return mean
    
    # REMOVE SMALL TRACKS
    def remove_small(self, context):
        t = time.time()
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        to_delete = []
        bpy.ops.clip.select_all(action='DESELECT')
        for track in tracks:
            if track.hide or track.lock:
                continue
            if len(track.markers) > 1:
                marker = track.markers.find_frame(last_frame)
                if marker is None and self.find_track_length(track) < props.small_tracks:
                    to_delete.append(track)
        deleted_tracks = len(to_delete)
        self.delete_tracks(to_delete)
        print("remove_small %.4f seconds %s tracks deleted." % (time.time()-t, deleted_tracks))
    
    def split_track(self, context, track, split_frame, skip=0):
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        if props.track_backwards:
            end = scene.frame_start
            step = -1
        else:
            end = scene.frame_end
            step = 1
        new_track = \
            tracks.new(frame=split_frame)
        for frame in range(split_frame, end, step):
            marker = track.markers.find_frame(frame)
            if marker is None:
                return
            # add new marker on new track for frame    
            if abs(frame - split_frame) >= skip:    
                new_marker = new_track.markers.find_frame(frame)
                if new_marker is None:
                    new_marker = new_track.markers.insert_frame(frame)
                new_marker.co = marker.co
            # remove marker on track for frame
            if frame == split_frame:
                track.hide = True
            else:
                track.markers.delete_frame(frame)
            marker.mute = True
                    
    # REMOVE JUMPING MARKERS
    def remove_jumping(self, context):
        
        t = time.time()
        
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        
        if props.track_backwards:
            step = -1
        else:
            step = 1
        
        to_split = [None for track in tracks]
        for frame in range(last_frame, current_frame, step):
            
            last = frame - step
            
            # mean motion (normalized [0-1]) distance for tracks between last and current frame
            mean = self.estimate_motion(context, last, frame)
            
            # how much a track is allowed to move 
            allowed = mean * props.jump_cut
        
            for i, track in enumerate(tracks):
                if track.hide or track.lock:
                    continue
                marker0 = track.markers.find_frame(frame)
                marker1 = track.markers.find_frame(last)
                if marker0 is not None and marker1 is not None:
                    distance = (marker0.co-marker1.co).length
                    # Jump Cut threshold
                    if distance > allowed:
                        if to_split[i] is None:
                            to_split[i] = [frame, frame]
                        else:
                            to_split[i][1] = frame 
        
        jumping = 0
        for i, split in enumerate(to_split):
            if split is not None:
                self.split_track(context, tracks[i], split[0], abs(split[0]-split[1]))
                jumping += 1
                    
        print("remove_jumping :%.4f seconds %s tracks cut." % (time.time()-t, jumping))  
    
    def setup_default_tracks_settings(self, context):
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        s = clip.tracking.settings
        s.default_frames_limit = props.frame_separation
        for track in tracks:
            track.frames_limit = props.frame_separation
    
    def modal(self, context, event):
        # prevent TIMER event while running
        print("modal start:%s %s" % (self.limits, event.type))
        
        if event.type in {'ESC'}:
            print("Cancelling")
            self.cancel(context)
            return {'FINISHED'}
        
        if event.type not in {'TIMER'}:
            return {'PASS_THROUGH'}
            
        self.stop_timer(context)
        scene, props, clip, tracks, current_frame, last_frame = self.get_vars_from_context(context)
        
        if props.track_backwards:
            end = scene.frame_start
            total = self.start_frame - end
        else:
            end = scene.frame_end
            total = end - self.start_frame
        self.progress = (current_frame-self.start_frame)/total
        
        if (((not props.track_backwards) and current_frame >= scene.frame_end) or
            (props.track_backwards and current_frame <= scene.frame_start)):
            self.cancel(context)
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
        
        # Remove bad tracks before adding new ones
        #if self.limits >= 3:
        self.remove_small(context)
        self.remove_jumping(context)
        
        # add new tracks
        # if current_frame % props.frame_separation == 0 or self.limits == 0:
        self.auto_features(context)

        # Select active trackers for tracking
        active_tracks = self.select_active_tracks(context)

        # finish if there is nothing to track
        if len(active_tracks) == 0:
            print("No new tracks created. Doing nothing.")
            self.progress = 0
            bpy.types.SpaceClipEditor.draw_handler_remove(self._handle, 'WINDOW')
            self.limits = 0
            self.show_tracks(context)    
            self.cancel(context)
            return {'FINISHED'}
            
        # Forwards or backwards tracking
        if props.track_backwards:
            self.track_frames_backward()
        else:
            self.track_frames_forward()
   
        # setup a timer to broadcast a TIMER event to force modal to re-run as fast as possible (not waiting for any mouse or keyboard event) 
        self.start_timer(context)
        print("modal end :%s" % (self.limits))
        self.limits += 1
        return {'RUNNING_MODAL'}
       
    def invoke(self, context, event):
        print("invoke %s" % (event.type))
        self.setup_default_tracks_settings(context)
        scene = context.scene
        self.start_frame = scene.frame_current
        self.start = (scene.frame_current-scene.frame_start) / (scene.frame_end-scene.frame_start)
        self.progress = 0
        self.limits = 0
        # draw progress
        args = (self, context)
        self._draw_handler = bpy.types.SpaceClipEditor.draw_handler_add(draw_callback, args, 'WINDOW', 'POST_PIXEL')
        self.start_timer(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def __init__(self):
        self.t = time.time()

    def __del__(self):
        print("AutoTrack %.2f seconds" % (time.time()-self.t))
        
    def execute(self, context):
        print("execute")
        return {'FINISHED'}
        
    def stop_timer(self, context):
        context.window_manager.event_timer_remove(self._timer)
    
    def start_timer(self, context):
        self._timer = context.window_manager.event_timer_add(time_step=0.1, window=context.window)
        
    def cancel(self, context):
        self.show_tracks(context)  
        bpy.types.SpaceClipEditor.draw_handler_remove(self._draw_handler, 'WINDOW')
        self.stop_timer(context)
        
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
