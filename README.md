##Blender Autotracker addon
![test tag](https://github.com/miikapuustinen/blender_autotracker/blob/master/images/autotracker_screenshot.jpg)
###What is it?
Python addon which introduces autotracking for Blender motion tracking. It automates marker creationg and feature detection, as well tries to cut down amount of bad tracks. It is more suitable for easier shots or can be used in conjunction with supervised tracking.

###How to install?
Drop autotracker.py to blender/scripts/addons/ folder or use User Preferences --> Add-ons Install from file to install.

###How to use?
1. Autotrack
2. Filter tracks
3. Solve


###Settings
Motion tracking --> Autotrack panel  
![alt tag](https://github.com/miikapuustinen/blender_autotracker/blob/master/images/autotracker_interface.jpg)
* Autotrack: Starts Autotracking.
* Track Backwards: When enabled autotracker tracks backwards.
* New Marker Threshold: How Close Are New Markers Allowed To Be Created (0-1).
* Frame Separation: Make New Markers Every Nth Frame
* Jump Threshold: How Much Tracks Can Jump Before They Are Muted (0-1).

####Detect Features Settings
These Settings Are The Same As Marker --> Detect Features.
* Margin: How Far From Edges New Markers Can Be Created.
* Threshold: Spacing For New Marker Creation
* Distance: How Far To Each Other New Markers Can Be Created
* Use Grease Pencil to mask areas to track: Whole frame, Inside Grease Pencil or Outside Grease Pencil.

#### Version 0.0.9