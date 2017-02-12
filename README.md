##Blender Autotracker addon

###What is it?
Blender addon which introduces autotracking for motion tracking. It automates marker creationg and feature detection, as well tries to cut down amount of bad tracks.

###How to install?
Drop autotracker.py to blender/scripts/addons/ folder or use User Preferences --> Add-ons Install from file to install.

###How to use?
![alt tag](https://github.com/miikapuustinen/blender_autotracker/blob/master/images/autotracker_interface.jpg)
* AUTOTRACK: Starts autotracking.
* NEW MARKER THRESHOLD: How close are new markers allowed to be created.
* FRAME SEPARATION: Make new markers every nth frame
* JUMP THRESHOLD: How much tracks can jump before they are muted (0-1).

####Detect Features Settings
These settings are the same as Marker-->Detect features.
* MARGIN: How far from edges new markers can be created.
* THRESHOLD: Spacing for new marker creation
* DISTANCE: How far to each other new markers can be created

#### Version 0.0.9