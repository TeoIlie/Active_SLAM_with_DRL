#!/usr/bin/env python3

import os
import numpy as np
from numpy import savetxt
import math
import subprocess
import json
import random
import sys
import time
import datetime
import yaml
import logging
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_srvs.srv import Empty
from geometry_msgs.msg import Twist
from ament_index_python.packages import get_package_share_directory
from pic4rl.sensors import Sensors
from pic4rl.utils.env_utils import *
from pic4rl.testing.nav_metrics import Navigation_Metrics


class Pic4rlEnvironmentLidar(Node):
    def __init__(self):
        """ """
        super().__init__("pic4rl_training_lidar")


        ########### Our parameters ##########
        self.slam_proc = None
        self.max_known = 20900
        #####################################


        self.declare_parameter("package_name", "pic4rl")
        self.declare_parameter("training_params_path", rclpy.Parameter.Type.STRING)
        self.declare_parameter("main_params_path", rclpy.Parameter.Type.STRING)
        self.package_name = (
            self.get_parameter("package_name").get_parameter_value().string_value
        )
        goals_path = os.path.join(
            get_package_share_directory(self.package_name), "goals_and_poses"
        )
        self.main_params_path = self.get_parameter("main_params_path").get_parameter_value().string_value
        train_params_path = self.get_parameter("training_params_path").get_parameter_value().string_value
        self.entity_path = os.path.join(
            get_package_share_directory("gazebo_sim"), "models/goal_box/model.sdf"
        )

        with open(train_params_path, "r") as train_param_file:
            train_params = yaml.safe_load(train_param_file)["training_params"]

        self.declare_parameters(
            namespace="",
            parameters=[
                ("mode", rclpy.Parameter.Type.STRING),
                ("data_path", rclpy.Parameter.Type.STRING),
                ("robot_name", rclpy.Parameter.Type.STRING),
                ("goal_tolerance", rclpy.Parameter.Type.DOUBLE),
                ("laser_param.max_distance", rclpy.Parameter.Type.DOUBLE),
                ("laser_param.num_points", rclpy.Parameter.Type.INTEGER),
                ("update_frequency", rclpy.Parameter.Type.DOUBLE),
                ("sensor", rclpy.Parameter.Type.STRING),
            ],
        )

        self.mode = self.get_parameter("mode").get_parameter_value().string_value
        # goals_path = os.path.join(goals_path, self.mode)
        self.data_path = (
            self.get_parameter("data_path").get_parameter_value().string_value
        )
        self.data_path = os.path.join(goals_path, self.data_path)
        print(train_params["--change_goal_and_pose"])
        self.change_episode = int(train_params["--change_goal_and_pose"])
        self.starting_episodes = int(train_params["--starting_episodes"])
        self.timeout_steps = int(train_params["--episode-max-steps"])
        self.robot_name = (
            self.get_parameter("robot_name").get_parameter_value().string_value
        )
        self.goal_tolerance = (
            self.get_parameter("goal_tolerance").get_parameter_value().double_value
        )
        self.lidar_distance = (
            self.get_parameter("laser_param.max_distance")
            .get_parameter_value()
            .double_value
        )
        self.lidar_points = (
            self.get_parameter("laser_param.num_points")
            .get_parameter_value()
            .integer_value
        )
        self.update_freq = (
            self.get_parameter("update_frequency").get_parameter_value().double_value
        )
        self.sensor_type = (
            self.get_parameter("sensor").get_parameter_value().string_value
        )

        qos = QoSProfile(depth=10)
        self.sensors = Sensors(self)
        log_path = os.path.join(get_package_share_directory(self.package_name),'../../../../', train_params["--logdir"])

        self.logdir = create_logdir(
            train_params["--policy"], self.sensor_type, log_path
        )
        self.get_logger().info(f"Logdir: {self.logdir}")

        if "--model-dir" in train_params:
            self.model_path = os.path.join(get_package_share_directory(self.package_name),'../../../../', train_params["--model-dir"])
        if "--rb-path-load" in train_params:
            self.rb_path_load = os.path.join(get_package_share_directory(self.package_name),'../../../../', train_params["--rb-path-load"])

        self.spin_sensors_callbacks() # this is the issue

        self.cmd_vel_pub = self.create_publisher(Twist, "cmd_vel", qos)

        self.reset_world_client = self.create_client(Empty, "reset_world")
        self.pause_physics_client = self.create_client(Empty, "pause_physics")
        self.unpause_physics_client = self.create_client(Empty, "unpause_physics")

        self.episode_step = 0
        self.previous_twist = Twist()
        self.episode = 0
        self.collision_count = 0
        self.t0 = 0.0
        self.evaluate = False
        self.index = 0

        self.initial_pose, self.goals, self.poses = self.get_goals_and_poses()
        self.goal_pose = self.goals[0]

        self.get_logger().info(f"Gym mode: {self.mode}")
        if self.mode == "testing":
            self.nav_metrics = Navigation_Metrics(self.logdir)
        self.get_logger().debug("PIC4RL_Environment: Starting process")
        self.prev_known = 0

    def step(self, action, episode_step=0):
        """ """
        twist = Twist()
        twist.linear.x = float(action[0])
        twist.angular.z = float(action[1])
        self.episode_step = episode_step

        observation, reward, done = self._step(twist)
        info = None

        return observation, reward, done, info

    def _step(self, twist=Twist(), reset_step=False):
        """ """
        self.get_logger().debug("sending action...")
        self.send_action(twist)

        self.get_logger().debug("getting sensor data...")
        self.spin_sensors_callbacks()
        (
            lidar_measurements,
            goal_info,
            robot_pose,
            collision,
            og_map
        ) = self.get_sensor_data()

        if not reset_step:
            if self.mode == "testing":
                self.nav_metrics.get_metrics_data(lidar_measurements, self.episode_step)

            self.get_logger().debug("checking events...")
            done, event = self.check_events(
                lidar_measurements, goal_info, robot_pose, collision
            )
            self.get_logger().debug("getting reward...")
            reward, curr_known, covered = self.get_reward(
                twist, lidar_measurements, goal_info, robot_pose, done, event, og_map
            )

            if covered:
                done = True

            self.prev_known = curr_known

            self.get_logger().debug("getting observation...")
            observation = self.get_observation(
                twist, lidar_measurements, goal_info, robot_pose
            )
        else:
            reward = None
            observation = None
            done = False
            event = None

        self.update_state(twist, lidar_measurements, goal_info, robot_pose, done, event)

        return observation, reward, done

    def get_goals_and_poses(self):
        """ """
        data = json.load(open(self.data_path, "r"))

        return data["initial_pose"], data["goals"], data["poses"]

    def spin_sensors_callbacks(self):
        """ """
        self.get_logger().debug("spinning node...")
        # rclpy.spin_once(self, timeout_sec=1.0) # added timeout_sec to prevent stuck, for now
        rclpy.spin_once(self)
        while None in self.sensors.sensor_msg.values():
            empty_measurements = [ k for k, v in self.sensors.sensor_msg.items() if v is None]
            self.get_logger().debug(f"empty_measurements: {empty_measurements}")
            # rclpy.spin_once(self, timeout_sec=1.0)
            rclpy.spin_once(self)
            self.get_logger().debug("spin once ...")
        self.sensors.sensor_msg = dict.fromkeys(self.sensors.sensor_msg.keys(), None)

    def send_action(self, twist):
        """ """
        
        self.cmd_vel_pub.publish(twist)
        # Regulate frequency of send action if needed
        freq, t1 = compute_frequency(self.t0)
        self.get_logger().debug(f"frequency : {freq}")
        self.t0 = t1
        if freq > self.update_freq:
            frequency_control(self.update_freq)

        # self.get_logger().debug("pausing...")
        # self.pause()

    def get_sensor_data(self):
        """ """

        sensor_data = {}
        sensor_data["scan"], collision = self.sensors.get_laser()
        sensor_data["odom"] = self.sensors.get_odom(vel=False)
        sensor_data["map"] = self.sensors.get_map()

        if sensor_data["scan"] is None:
            sensor_data["scan"] = (
                np.ones(self.lidar_points) * self.lidar_distance
            ).tolist()
        if sensor_data["odom"] is None:
            sensor_data["odom"] = [0.0, 0.0, 0.0]

        goal_info, robot_pose = process_odom(self.goal_pose, sensor_data["odom"])
        lidar_measurements = sensor_data["scan"]
        og_map = sensor_data["map"]

        return lidar_measurements, goal_info, robot_pose, collision, og_map

    def check_events(self, lidar_measurements, goal_info, robot_pose, collision):
        """ """
        if collision:
            self.collision_count += 1
            if self.collision_count >= 3:
                self.collision_count = 0
                self.get_logger().info(
                    f"Ep {'evaluate' if self.evaluate else self.episode+1}: Collision"
                )
                logging.info(
                    f"Ep {'evaluate' if self.evaluate else self.episode+1}: Collision"
                )
                return True, "collision"
            else:
                return False, "None"

        if goal_info[0] < self.goal_tolerance:
            self.get_logger().info(
                f"Ep {'evaluate' if self.evaluate else self.episode+1}: Goal"
            )
            logging.info(f"Ep {'evaluate' if self.evaluate else self.episode+1}: Goal")
            return True, "goal"

        if self.episode_step + 1 == self.timeout_steps:
            self.get_logger().info(
                f"Ep {'evaluate' if self.evaluate else self.episode+1}: Timeout"
            )
            logging.info(
                f"Ep {'evaluate' if self.evaluate else self.episode+1}: Timeout"
            )
            return True, "timeout"

        return False, "None"

    def get_reward(self, twist, lidar_measurements, goal_info, robot_pose, done, event, og_map):
        """ """
        # hyperparams
        info_gain_coeff = 1.5
        info_gain_beta = 10
        collision_penalty = -20
        max_known_reward = 100
        covered = False

        # info gain
        total_known = 0

        for cell in og_map:
            if cell == 0 or cell == 1:
                total_known += 1

        info_gain = total_known - self.prev_known

        print(f"================ Raw Info Gain:{info_gain}")

        info_gain = info_gain_coeff * np.emath.logn(10, 1.0 + info_gain_beta * info_gain)
        # 1.5 * log_10(10x + 1) 

        print(f"================ Info Gain reward:{info_gain}")

        if info_gain >= 0:
            print(f"Abdeali is happy!")
        else:
            print(f"\n\nAbdeali sad :(((\n\n")
            info_gain = 0 #TODO find why Abdeali gets sad

        print(f"================ Total known:{total_known}, Prev known:{self.prev_known}")

        reward = info_gain

        # collision
        collision = False
        if event == "collision":
            reward += collision_penalty
            collision = True
        
        # coverage
        if total_known >= 0.97 * self.max_known:
            reward += max_known_reward
            covered = True

        print(f"================ Reward:{reward}, Collision:{collision}")
        return reward, total_known, covered

    def get_observation(self, twist, lidar_measurements, goal_info, robot_pose):
        """ """
        state_list = goal_info


        state = np.array(state_list, dtype=np.float32)

        return state

    def update_state(
        self, twist, lidar_measurements, goal_info, robot_pose, done, event
    ):
        """ """
        self.previous_twist = twist
        self.previous_lidar_measurements = lidar_measurements
        self.previous_goal_info = goal_info
        self.previous_robot_pose = robot_pose

    def reset(self, n_episode, tot_steps, evaluate=False):
        """ """
        if self.mode == "testing":
            self.nav_metrics.calc_metrics(n_episode, self.initial_pose, self.goal_pose)
            self.nav_metrics.log_metrics_results(n_episode)
            self.nav_metrics.save_metrics_results(n_episode)

        self.episode = n_episode
        self.evaluate = evaluate
        logging.info(
            f"Total_episodes: {n_episode}{' evaluation episode' if self.evaluate else ''}, Total_steps: {tot_steps}, episode_steps: {self.episode_step+1}\n"
        )
        print()
        self.get_logger().info("Initializing new episode ...")
        logging.info("Initializing new episode ...")
        self.new_episode()
        self.get_logger().debug("Performing null step to reset variables")
        self.episode_step = 0

        _, _, _ = self._step(reset_step=True)
        observation, _, _ = self._step()

        return observation

    def new_episode(self):
        """ """
        print("\n\n\n======New Episode=======\n\n\n")
        self.get_logger().debug("Resetting simulation ...")
        req = Empty.Request()

        while not self.reset_world_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("service not available, waiting again...")
        self.reset_world_client.call_async(req)

        if self.slam_proc is not None:
            # self.slam_proc.terminate()
            self.get_logger().info("Killing any existing slam_toolbox processes...")
            subprocess.run(['pkill', '-f', 'slam_toolbox'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)  # Give time for OS cleanup
            # self.slam_proc.kill()
            # self.slam_proc.wait()

        self.slam_proc = subprocess.Popen(['ros2', 'launch', 'slam_toolbox', 'online_async_launch.py'], 
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

        self.prev_known = 0

        if self.episode % self.change_episode == 0.0 or self.evaluate:
            self.index = int(np.random.uniform() * len(self.poses)) - 1

        self.get_logger().debug("Respawning robot ...")
        self.respawn_robot(self.index)

        self.get_logger().debug("Respawning goal ...")
        self.respawn_goal(self.index)

        self.get_logger().debug("Environment reset performed ...")

    def respawn_goal(self, index):
        """ """
        if self.episode <= self.starting_episodes:
            self.get_random_goal()
        else:
            self.get_goal(index)

        self.get_logger().info(
            f"Ep {'evaluate' if self.evaluate else self.episode+1} goal pose [x, y]: {self.goal_pose}"
        )
        logging.info(
            f"Ep {'evaluate' if self.evaluate else self.episode+1} goal pose [x, y]: {self.goal_pose}"
        )


    def get_goal(self, index):
        """ """
        self.goal_pose = self.goals[index]

    def get_random_goal(self):
        """ """
        if self.episode < 6 or self.episode % 25 == 0:
            x = 0.55
            y = 0.55
        else:
            x = random.randrange(-29, 29) / 10.0
            y = random.randrange(-29, 29) / 10.0

        x += self.initial_pose[0]
        y += self.initial_pose[1]

        self.goal_pose = [x, y]

    def respawn_robot(self, index):
        """ """
        if self.episode <= self.starting_episodes:
            x, y, yaw = tuple(self.initial_pose)
        else:
            x, y, yaw = tuple(self.initial_pose) #TODO change back

        qz = np.sin(yaw / 2)
        qw = np.cos(yaw / 2)

        self.get_logger().info(
            f"Ep {'evaluate' if self.evaluate else self.episode+1} robot pose [x,y,yaw]: {[x, y, yaw]}"
        )
        logging.info(
            f"Ep {'evaluate' if self.evaluate else self.episode+1} robot pose [x,y,yaw]: {[x, y, yaw]}"
        )

        position = (
            "position: {x: " + str(x) + ",y: " + str(y) + ",z: " + str(0.07) + "}"
        )
        orientation = "orientation: {z: " + str(qz) + ",w: " + str(qw) + "}"
        pose = position + ", " + orientation
        state = "'{state: {name: '" + self.robot_name + "',pose: {" + pose + "}}}'"
        subprocess.run(
            "ros2 service call /test/set_entity_state gazebo_msgs/srv/SetEntityState "
            + state,
            shell=True,
            stdout=subprocess.DEVNULL,
        )
        time.sleep(0.25)

    def pause(self):
        """ """
        req = Empty.Request()
        while not self.pause_physics_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("service not available, waiting again...")
        future = self.pause_physics_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

    def unpause(self):
        """ """
        req = Empty.Request()
        while not self.unpause_physics_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("service not available, waiting again...")
        future = self.unpause_physics_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
