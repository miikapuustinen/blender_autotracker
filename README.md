## Blender Autotracker addon
![test tag](https://github.com/miikapuustinen/blender_autotracker/blob/master/images/autotracker_screenshot.jpg)
### What is it?
Python addon which introduces autotracking for Blender motion tracking. It automates marker creationg and feature detection, as well tries to cut down amount of bad tracks. It is more suitable for easier shots or can be used in conjunction with supervised tracking.

### How to install?
Drop autotracker.py to blender/scripts/addons/ folder or use User Preferences --> Add-ons Install from file to install.

### How to use?
1. Autotrack
2. Clean up tracks
3. Solve

### Settings
Motion tracking --> Autotrack panel  
![alt tag](https://github.com/miikapuustinen/blender_autotracker/blob/master/images/autotracker_interface.jpg)
* Autotrack: Starts Autotracking.
* Track Backwards: When enabled autotracker tracks backwards.
* Minimum Track Length: Delete tracks shorter than this number of frames (0 = Keep all tracks).
* New Marker Threshold: Threshold how near new features can appear during autotracking.
* Frame Separation: How often new features are generated.
* Jump Threshold: Distance how much a marker can travel before it's considered to be a bad track and cut (Factor relative to mean motion). A new track is added.

#### Detect Features Settings
* Margin: Margin how far from edges new features need to be when created.
* Threshold: Theshold level to consider to be good enough for tracking.
* Distance: Minimum distance accepted between new features.
* Feature Placement: Use Grease Pencil to mask areas to track. Whole frame, Inside Grease Pencil or Outside Grease Pencil.

#### Version 0.0.9
