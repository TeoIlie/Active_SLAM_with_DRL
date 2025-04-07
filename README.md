# Active Exploration in SLAM: a Deep Reinforcement Learning Approach
## Changes Summary
- this repo is based on the [PIC4rl](https://github.com/PIC4SeR/PIC4rl_gym) library 
- major modifications:
  - new task definition in `cisc856_ws/src/PIC4rl_gym/pic4rl/pic4rl/tasks/Mapping_ours`, including reward re-definition
  - parameter modifications in `cisc856_ws/src/PIC4rl_gym/pic4rl/config`
  - new world definition in `cisc856_ws/src/PIC4rl_gym/gazebo_sim/worlds/tiny.world`
  - new LiDAR sensor definition in `cisc856_ws/src/PIC4rl_gym/pic4rl/pic4rl/sensors.py`
- training, testing video available [here](https://youtu.be/ueNf1zpZSVA)
