#based off of reinforcement learning env code

from os.path import dirname, join, abspath
from pyrep import PyRep
from pyrep.robots.arms.panda import Panda
from pyrep.objects.shape import Shape
from pyrep.const import PrimitiveShape
from pyrep.errors import ConfigurationPathError
from pyrep.objects.dummy import Dummy
from pyrep.objects.vision_sensor import VisionSensor
import numpy as np
import math
import pandas as pd
import os
import PIL
from PIL import Image
from pyrep.objects.joint import JointMode



#Setup
SCENE_FILE = join(dirname(abspath(__file__)), "simulations/scene_panda_reach_target.ttt")
EPISODE = 25 #number of total episodes to run
RUNS = 4 #number of total different approaches to take
EPISODE_LENGTH = 100 #number of total steps to reach the target




class Environment(object):

    def __init__(self):
        #launch pyrep
        self.pr = PyRep()
        self.pr.launch(SCENE_FILE, headless = False)
        self.pr.start()
        #--Robot
        self.agent = Panda()
        # self.agent.set_control_loop_enabled(False)
        # self.agent.set_motor_locked_at_zero_velocity(True)
        self.agent_ee_tip = self.agent.get_tip()
        self.initial_joint_positions = self.agent.get_joint_positions()
        self.agent_state = self.agent.get_configuration_tree()


        #--Vision Sensor
        self.vs = VisionSensor("Vision_sensor")
        self.vs.set_resolution([64, 64])

        #--Cube
        self.cube = Shape.create(type=PrimitiveShape.CUBOID,
                      size=[0.05, 0.05, 0.05],
                      color=[1.0, 0.1, 0.1],
                      static=True, respondable=False)
        self.target = Dummy.create()

        #--Cube Spawn
        cube_size = .1
        self.table = Shape('diningTable_visible')
        cube_min_max = self.table.get_bounding_box()
        cube_min_max = [cube_min_max[0] + cube_size,
                        .6 - cube_size,
                        cube_min_max[2] + cube_size,
                        cube_min_max[3] - cube_size,
                        cube_min_max[5] - .05]
        self.position_min, self.position_max = [cube_min_max[0], cube_min_max[2], cube_min_max[3]], [cube_min_max[1],
                                                                                           cube_min_max[3],
                                                                                           cube_min_max[3]]
        self.target_min, self.target_max = [-.03, -.03, 0], [.03, .03, .03]

        col_name = ["imLoc", "jVel", "jPos", "eeVel", "eePos", "cPos"]
        self.df = pd.DataFrame(columns=col_name)
        self.path=None
        self.path_step = None
    def setup(self):
        # self.pr.stop()
        # self.pr.start()

        #----general scene stuff

        # self.agent.set_model_dynamic(False)
        # self.agent.set_control_loop_enabled(False)
        # self.agent.set_motor_locked_at_zero_velocity(True)
        # self.agent_ee_tip = self.agent.get_tip()
        self.agent.set_joint_target_velocities(np.zeros_like(self.agent.get_joint_target_velocities()))
        # self.agent.set_joint_positions(self.initial_joint_positions)
        # self.agent.set_model_dynamic(True)
        # self.vs = VisionSensor("Vision_sensor")
        # self.vs.set_resolution([64, 64])
        # self.cube = Shape.create(type=PrimitiveShape.CUBOID,
        #               size=[0.05, 0.05, 0.05],
        #               color=[1.0, 0.1, 0.1],
        #               static=True, respondable=False)
        # self.target = Dummy.create()

        #----Dynamic and config tree reset
        self.agent.reset_dynamic_object()
        self.pr.set_configuration_tree(self.agent_state)

        #----Robot Pose Reset
        self.agent.set_joint_positions(self.initial_joint_positions,disable_dynamics=True)
        self.path=None
        self.path_step = None


    def replaceCube(self):
        pos = list(np.random.uniform(self.position_min, self.position_max))
        self.cube.set_position(pos, self.table)
        try:
            pp = self.agent.get_linear_path(
                position=self.cube.get_position(),
                euler=[0, math.radians(180), 0],
                steps=100
            )
        except ConfigurationPathError as e:
            print("Cube bad placement. Replacing.")
            self.replaceCube()
        self.replaceTarget()
    def replaceTarget(self):
        targpos = list(np.random.uniform(self.target_min, self.target_max))
        self.target.set_position(targpos, self.cube)
        try:
            self.path = self.agent.get_linear_path(
                position=self.target.get_position(),
                euler=[0, math.radians(180), math.radians(90)],
                steps=100
            )
        except ConfigurationPathError as e:
            print("Cube bad placement. Replacing.")
            self.replaceTarget()
    def gatherInfo(self,ep,r,s):
        im = self.vs.capture_rgb()
        if not os.path.isdir(f"images/episode{ep}"):
            os.mkdir(f"images/episode{ep}")
        if not os.path.isdir(f"images/episode{ep}/run{r}"):
            os.mkdir(f"images/episode{ep}/run{r}")
        location = f"images/episode{ep}/run{r}/s{s}.jpg"
        im = Image.fromarray((im * 255).astype(np.uint8)).resize((64, 64)).convert('RGB')
        im.save(location)

        joint_vel = ",".join(np.array(self.agent.get_joint_velocities()).astype(str))
        joint_pos = ",".join(np.array(self.agent.get_joint_positions()).astype(str))
        ee_pos = ",".join(self.agent.get_tip().get_position(relative_to=self.agent).astype(str))
        ee_vel = ",".join(np.concatenate(list(self.agent.get_tip().get_velocity()), axis=0).astype(str))
        cube_pos = ",".join(self.cube.get_position(relative_to=self.agent).astype(str))

        line = [location, joint_vel, joint_pos, ee_vel, ee_pos, cube_pos]
        df_length = len(self.df)
        self.df.loc[df_length] = line
    def get_path(self):
        self.path = self.agent.get_linear_path(
            position=self.target.get_position(), euler=[0, math.radians(180), math.radians(90)], steps=100)
        self.path_step = self.path._path_points
        # print(self.path_step)
    def step(self):
        done = self.path.step()
        self.pr.step()
        return done

    def shutdown(self):
        self.pr.stop()
        self.pr.shutdown()







env = Environment()
for e in range(EPISODE):
    env.setup()
    env.replaceCube()
    for r in range(RUNS):
        env.setup()
        env.replaceTarget()
        # env.get_path()
        done=False
        sq=0
        while not done:
            done = env.step()
            env.gatherInfo(e,r,sq)
            sq+=1

env.df.to_csv("lol.csv")


