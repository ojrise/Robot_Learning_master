"""
This file implements a wrapper for facilitating compatibility with OpenAI gym.
This is useful when using these environments with code that assumes a gym-like 
interface.
"""

import numpy as np
from gym import spaces
from gym.core import Env
from robosuite.wrappers import Wrapper
from stable_baselines3.common.preprocessing import get_flattened_obs_dim, is_image_space


class GymWrapper_multiinput(Wrapper, Env):
    """
    Initializes the Gym wrapper. Mimics many of the required functionalities of the Wrapper class
    found in the gym.core module

    Args:
        env (MujocoEnv): The environment to wrap.
        keys (None or list of str): If provided, each observation will
            consist of concatenated keys from the wrapped environment's
            observation dictionary. Defaults to proprio-state and object-state.

    Raises:
        AssertionError: [Object observations must be enabled if no keys]
    """

    def __init__(self, env, keys=None, smaller_action_space = False):
        # Run super method
        super().__init__(env=env)
        # Create name for gym
        robots = "".join([type(robot.robot_model).__name__ for robot in self.env.robots])
        self.name = robots + "_" + type(self.env).__name__

        # Get reward range
        self.reward_range = (0, self.env.reward_scale)

        self.smaller_action_space = smaller_action_space

        if keys is None:
            keys = []
            # Add object obs if requested
            if self.env.use_object_obs:
                keys += ["object-state"]
            # Add image obs if requested
            if self.env.use_camera_obs:
                keys += [f"{cam_name}_image" for cam_name in self.env.camera_names]
            # Iterate over all robots to add to state
            for idx in range(len(self.env.robots)):
                keys += ["robot{}_proprio-state".format(idx)]
        self.keys = keys

        # Gym specific attributes
        self.env.spec = None
        self.metadata = None

        # set up observation and action spaces
        obs = self.env.reset()
        #self.modality_dims = {key: obs[key].shape for key in self.keys}

        observation_space_dict = {}
        image_list = []

        for cam_name in self.env.camera_names:
            key = cam_name + "_image"
            if key in self.keys:
                self.keys.remove(key)
                image_list.append(key)
                low, high = 0, 255
                d_type = np.uint8

                observation_space_dict.update({key: spaces.Box(low = low,high = high, shape=(obs[key].shape), dtype= d_type)})

        for key in self.keys:
            low, high = -np.inf, np.inf
            d_type = np.float32
            
            #mulig jeg må vurdere å flate ut         
            observation_space_dict.update({key: spaces.Box(low = low,high = high, shape=(obs[key].shape), dtype= d_type)})

        self.observation_space = spaces.Dict(observation_space_dict)
        
        #print(self.observation_space)

        low, high = self.env.action_spec
        if self.smaller_action_space:
            low, high = low[:-2], high[:-2] #trekker fra a og b som mulige inputs
        self.action_space = spaces.Box(low=np.float32(low), high=np.float32(high))

        for key in image_list:
            self.keys.insert(0,key)

        #variable for checking grasp sucess
        self.grasp_success = 0

    def _multiinput_obs(self, obs_dict, verbose=False):
        """
        Filters keys of interest out and concatenate the information.

        Args:
            obs_dict (OrderedDict): ordered dictionary of observations
            verbose (bool): Whether to print out to console as observation keys are processed

        Returns:
            np.array: observations flattened into a 1d array
        """
        ob_lst = {}
        for key in self.keys:
            if key in obs_dict:
                if verbose:
                    print("adding key: {}".format(key))
                ob_lst.update({key: obs_dict[key]})
        return ob_lst
    

    def reset(self):
        """
        Extends env reset method to return flattened observation instead of normal OrderedDict.

        Returns:
            np.array: Flattened environment observation space after reset occurs
        """
        self.grasp_success = 0

        ob_dict = self.env.reset()
        return self._multiinput_obs(ob_dict)

    def step(self, action):
        """
        Extends vanilla step() function call to return flattened observation instead of normal OrderedDict.

        Args:
            action (np.array): Action to take in environment

        Returns:
            4-tuple:

                - (np.array) flattened observations from the environment
                - (float) reward from the environment
                - (bool) whether the current episode is completed or not
                - (dict) misc information
        """
        if self.smaller_action_space:
            action = np.insert(action, 3, 0)
            action = np.insert(action, 4, 0)

        ob_dict, reward, done, info = self.env.step(action)

        # It will now keep being 1 until reset
        if self.env._check_success():
            print("succesful_grasp")
            self.grasp_success = 1
        
        info["is_success"] = self.grasp_success

        return self._multiinput_obs(ob_dict), reward, done, info

    def seed(self, seed=None):
        """
        Utility function to set numpy seed

        Args:
            seed (None or int): If specified, numpy seed to set

        Raises:
            TypeError: [Seed must be integer]
        """
        # Seed the generator
        if seed is not None:
            try:
                np.random.seed(seed)
            except:
                TypeError("Seed must be an integer type!")

    def compute_reward(self, achieved_goal, desired_goal, info):
        """
        Dummy function to be compatible with gym interface that simply returns environment reward

        Args:
            achieved_goal: [NOT USED]
            desired_goal: [NOT USED]
            info: [NOT USED]

        Returns:
            float: environment reward
        """
        # Dummy args used to mimic Wrapper interface
        return self.env.reward()
