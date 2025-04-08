# Active Exploration in SLAM: a Deep Reinforcement Learning Approach

## Demo 🤖
![map_image](/images/demo.gif?raw=true "Map Image")

## Quick Start
1. on Ubuntu 22.04, download required packages:
    - [ROS2 Humble](https://docs.ros.org/en/humble/Installation/Alternatives/Ubuntu-Development-Setup.html)
    - [Gazebo Fortress](https://gazebosim.org/docs/fortress/install_ubuntu/) 
    - [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox?tab=readme-ov-file#install)
2. clone this repo
3. optionally, adjust testing and training parameters in `cisc856_ws/src/PIC4rl_gym/pic4rl/config`
3. run simulation launch files:
    - Gazebo launch file at `cisc856_ws/run_gazebo_sim.sh`
    - PIC4rl launch file at `cisc856_ws/run_pic4rl_launch.sh` - this also launches SLAM Toolbox  
4. optionally, open Rviz and subscribe to the **map** topic to visualize the SLAM occupancy grid in real-time

## Changes Summary
- this repo is based on the [PIC4rl](https://github.com/PIC4SeR/PIC4rl_gym) library 
- major modifications:
  - new task definition in `cisc856_ws/src/PIC4rl_gym/pic4rl/pic4rl/tasks/Mapping_ours`, including reward re-definition
  - parameter modifications in `cisc856_ws/src/PIC4rl_gym/pic4rl/config`
  - new world definition in `cisc856_ws/src/PIC4rl_gym/gazebo_sim/worlds/tiny.world`
  - new LiDAR sensor definition in `cisc856_ws/src/PIC4rl_gym/pic4rl/pic4rl/sensors.py`
- training, testing video available [here](https://youtu.be/ueNf1zpZSVA)
