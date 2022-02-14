import robosuite as suite
import numpy as np

from environments import Lift_4_objects

from robosuite.environments.base import register_env
from robosuite import load_controller_config
from robosuite.wrappers import GymWrapper

from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize


def wrap_env(env):
    wrapped_env = Monitor(env)                          # Needed for extracting eprewmean and eplenmean
    wrapped_env = DummyVecEnv([lambda : wrapped_env])   # Needed for all environments (e.g. used for mulit-processing)
    wrapped_env = VecNormalize(wrapped_env)             # Needed for improving training when using MuJoCo envs?
    return wrapped_env

#Registrerer custom environment
register_env(Lift_4_objects)

config = load_controller_config(default_controller="OSC_POSE")


env = GymWrapper(
        suite.make(
            env_name="Lift_4_objects",
            robots = "IIWA",
            controller_configs = config, 
            gripper_types="Robotiq85Gripper",      
            has_renderer=False,                    
            has_offscreen_renderer=True,           
            control_freq=500,                       
            horizon=1000,
            camera_heights = 48,
            camera_width = 48,                          
            use_object_obs=False,                  
            use_camera_obs=True,                   
        ), ["agentview_image"]
)

env = wrap_env(env)

#Denne koden sjekker om environmentet er godkjent for å trene med stable_baseline
#check_env(env)

print("Getting observations")

obs = env.reset()
action = [env.action_space.sample()]
obs, reward, done, info = env.step(action)
print(obs.shape) # obs er en tuple

#image = np.reshape(obs, (256,256,3))
print("Observation = {} \n\n Action = {} \n\n".format(obs,action))
