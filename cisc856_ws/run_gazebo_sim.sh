#!/bin/bash

# Script to run ROS2/Gazebo simulation with a termination condition

# Exit on any error
set -e

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Define timeout in seconds (e.g., 300 seconds = 5 minutes)
TIMEOUT=300000

# Function to clean up and terminate processes
cleanup() {
    echo -e "${GREEN}Terminating Gazebo and ROS2 launch...${NC}"
    # Kill the ROS2 launch process if it exists
    if [ -n "$LAUNCH_PID" ]; then
        kill -SIGINT $LAUNCH_PID 2>/dev/null
        wait $LAUNCH_PID 2>/dev/null
        echo "ROS2 launch process terminated."
    fi
    # Kill Gazebo processes
    pkill -f "gzserver" 2>/dev/null
    pkill -f "gzclient" 2>/dev/null
    echo "Gazebo processes terminated."
    exit 0
}

# Trap Ctrl+C (SIGINT) and call cleanup function
trap cleanup SIGINT

# Step 1: Source Gazebo setup
echo -e "${GREEN}Sourcing Gazebo setup...${NC}"
if [ -f "/usr/share/gazebo/setup.bash" ]; then
    source /usr/share/gazebo/setup.bash
    echo "Gazebo setup sourced successfully."
else
    echo -e "${RED}Error: /usr/share/gazebo/setup.bash not found!${NC}"
    exit 1
fi

# Step 2: Source ROS2 workspace setup
echo -e "${GREEN}Sourcing ROS2 workspace setup...${NC}"
if [ -f "install/local_setup.bash" ]; then
    source install/local_setup.bash
    echo "ROS2 workspace setup sourced successfully."
else
    echo -e "${RED}Error: install/local_setup.bash not found!${NC}"
    echo "Make sure you are in the correct ROS2 workspace directory and have built it."
    exit 1
fi

# Step 3: Launch the ROS2 Gazebo simulation in the background
echo -e "${GREEN}Launching ROS2 Gazebo simulation...${NC}"
ros2 launch gazebo_sim simulation.launch.py &
LAUNCH_PID=$!

# Check if the launch started successfully
if ! ps -p $LAUNCH_PID > /dev/null; then
    echo -e "${RED}Error: Failed to start simulation.launch.py${NC}"
    exit 1
fi
echo "Simulation launched with PID: $LAUNCH_PID"

# Step 4: Termination condition
echo -e "${GREEN}Simulation running. Press Ctrl+C to terminate, or it will auto-terminate in $TIMEOUT seconds.${NC}"

# Wait for either timeout or user interruption
sleep $TIMEOUT &  # Run sleep in background to allow Ctrl+C to interrupt
SLEEP_PID=$!
wait $SLEEP_PID 2>/dev/null

# If timeout is reached, trigger cleanup
echo "Timeout reached ($TIMEOUT seconds)."
cleanup