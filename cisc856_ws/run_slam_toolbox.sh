#!/bin/bash

# Script to set up ROS2 environment, launch pic4rl_starter.launch.py, and handle termination

# Exit on any error
set -e

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Define timeout in seconds (e.g., 300 seconds = 5 minutes)
TIMEOUT=300

# Function to clean up and terminate processes
cleanup() {
    echo -e "${GREEN}Terminating ROS2 launch...${NC}"
    # Kill the ROS2 launch process if it exists
    if [ -n "$LAUNCH_PID" ]; then
        kill -SIGINT $LAUNCH_PID 2>/dev/null
        wait $LAUNCH_PID 2>/dev/null
        echo "ROS2 launch process terminated."
    fi
    exit 0
}

# Trap Ctrl+C (SIGINT) and call cleanup function
trap cleanup SIGINT

# Step 1: Source ROS2 workspace setup
echo -e "${GREEN}Sourcing ROS2 workspace setup...${NC}"
if [ -f "install/local_setup.bash" ]; then
    source install/local_setup.bash
    echo "ROS2 workspace setup sourced successfully."
else
    echo -e "${RED}Error: install/local_setup.bash not found!${NC}"
    echo "Make sure you are in the correct ROS2 workspace directory and have built it."
    exit 1
fi

# Step 2: Launch the ROS2 pic4rl starter in the background
echo -e "${GREEN}Launching ROS2 pic4rl starter...${NC}"
ros2 launch slam_toolbox online_async_launch.py &
LAUNCH_PID=$!

# Check if the launch started successfully
if ! ps -p $LAUNCH_PID > /dev/null; then
    echo -e "${RED}Error: Failed to start pic4rl_starter.launch.py${NC}"
    exit 1
fi
echo "Simulation launched with PID: $LAUNCH_PID"

# Step 3: Termination condition
echo -e "${GREEN}Simulation running. Press Ctrl+C to terminate, or it will auto-terminate in $TIMEOUT seconds.${NC}"

# Wait for either timeout or user interruption
sleep $TIMEOUT &  # Run sleep in background to allow Ctrl+C to interrupt
SLEEP_PID=$!
wait $SLEEP_PID 2>/dev/null

# If timeout is reached, trigger cleanup
echo "Timeout reached ($TIMEOUT seconds)."
cleanup