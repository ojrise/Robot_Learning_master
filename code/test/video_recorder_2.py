from email import policy
from locale import normalize
from unicodedata import name
import numpy as np
import robosuite as suite
import os
import yaml

import numpy as np
import imageio
import robosuite.utils.macros as macros
from scipy import ndimage
import matplotlib.pyplot as plt
from PIL import Image


from robosuite.models.robots.robot_model import register_robot
from robosuite.environments.base import register_env

from stable_baselines3 import PPO, SAC
from stable_baselines3.common.save_util import save_to_zip_file, load_from_zip_file
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecTransposeImage
from stable_baselines3.common.vec_env.vec_normalize import VecNormalize

from src.environments import Lift_4_objects, Lift_edit
from src.models.robots.manipulators.iiwa_14_robot import IIWA_14, IIWA_14_modified, IIWA_14_modified_flange, IIWA_14_modified_flange_joint_limit
from src.models.grippers.robotiq_85_iiwa_14_gripper import Robotiq85Gripper_iiwa_14, Robotiq85Gripper_iiwa_14_longer_finger
from src.helper_functions.register_new_models import register_gripper, register_robot_class_mapping
from src.helper_functions.wrap_env import make_multiprocess_env, make_singel_env
from src.helper_functions.camera_functions import adjust_width_of_image

def record_video(env, model, video_length,num_episodes, fps, name_of_video_file):
    macros.IMAGE_CONVENTION = "opencv"
    # create a video writer with imageio
    writer = imageio.get_writer(name_of_video_file+".mp4", fps=fps)

    for j in range(num_episodes):
        obs = env.reset()
        print("new_episode")
        suc_val = 1
        #reward_plot = []
        #step_plot = []
        for i in range(video_length+10):

            action = model.predict(obs)
            obs, reward, done, info = env.step(action)
            if info[0]["is_success"] >= suc_val:
                print("object_is_lifted_at_step", i)
                suc_val += 0.1
            #reward_plot.append(reward)
            #step_plot.append(i)
            frame = obs["custom" + "_image"][0]
            img = Image.fromarray(frame, 'RGB')
            img = img.rotate(180)

            frame = np.asarray(img)
            #frame = ndimage.rotate(frame, 180)
            writer.append_data(frame)
            # if done:
            #     plt.plot(step_plot,reward_plot)
            #     plt.xlabel('Reward')
            #     plt.ylabel('Timestep')
            #     plt.title(str(j) + "epsiode")
            #     plt.savefig(name_of_video_file + "_plot_" + str(j+1))
            #     plt.show()

            #     break

    writer.close()


if __name__ == '__main__':
    register_robot(IIWA_14_modified)
    register_robot(IIWA_14)
    register_robot(IIWA_14_modified_flange)
    register_robot(IIWA_14_modified_flange_joint_limit)
    register_gripper(Robotiq85Gripper_iiwa_14)
    register_gripper(Robotiq85Gripper_iiwa_14_longer_finger)
    register_robot_class_mapping("IIWA_14")
    register_robot_class_mapping("IIWA_14_modified")
    register_robot_class_mapping("IIWA_14_modified_flange")
    register_robot_class_mapping("IIWA_14_modified_flange_joint_limit")
    register_env(Lift_edit)
    register_env(Lift_4_objects)



    yaml_file = "config_files/" + input("Which yaml file to load config from: ")
    ###########yaml_file = "config_files/ppo_test.yaml" 
    with open(yaml_file, 'r') as stream:
        config = yaml.safe_load(stream)
        
    answer = input("Have you dobbel checked if you are using the correct load files? \n  [y/n] ") 
    if answer != "y":
        exit()

    num_episodes = int(input("How many epsiodes do you want to record?   "))
    name_of_video_file = input("What should video file be called?   ") 


    # Environment specifications
    env_options = config["robosuite"]
    env_options["custom_camera_trans_matrix"] = np.array(env_options["custom_camera_trans_matrix"])
    env_id = env_options.pop("env_id")

    #Video_settings
    control_freq = env_options['control_freq']
    horizon = env_options['horizon']

    #normalize obs and rew
    
    normalize_obs = config['normalize_obs']
    normalize_rew = config['normalize_rew']
    norm_obs_keys = config['norm_obs_keys']


    # Observations
    obs_config = config["gymwrapper"]
    obs_list = obs_config["observations"] 
    smaller_action_space = obs_config["smaller_action_space"]
    xyz_action_space = obs_config["xyz_action_space"]

    # Settings for stable-baselines RL algorithm
    sb_config = config["sb_config"]
    training_timesteps = sb_config["total_timesteps"]
    num_procs = sb_config["num_procs"]
    policy = sb_config["policy"]

    # Settings for stable-baselines policy
    policy_kwargs = config["sb_policy"]
    policy_type = policy_kwargs.pop("type")

    # Settings used for file handling and logging (save/load destination etc)
    file_handling = config["file_handling"]

    save_model_folder = file_handling["save_model_folder"]
    save_model_filename = file_handling["save_model_filename"]
    load_model_folder = file_handling["load_model_folder"]
    load_model_filename = file_handling["load_model_filename"]

    # Join paths
    save_model_path = os.path.join(save_model_folder, save_model_filename)
    save_vecnormalize_path = os.path.join(save_model_folder, 'vec_normalize_' + save_model_filename + '.pkl')

    # Settings for pipeline
    seed = config["seed"]

    #Create ENV
    print("making")
    num_procs = 1   #overwrites the yaml file in order 
    env = (SubprocVecEnv([make_multiprocess_env(env_id, env_options, obs_list, smaller_action_space, xyz_action_space,  i, seed) for i in range(num_procs)]))
    #env = make_multiprocess_env(env_id, env_options, obs_list, smaller_action_space,  i, seed)


    load_model_path = os.path.join(load_model_folder, load_model_filename)
    load_vecnormalize_path = os.path.join(load_model_folder, 'vec_normalize_' + load_model_filename + '.pkl')

    normalize_env = str(input("Do you want to make a new normalized env or load from file? \n  [make_new/load_file]"))

    if normalize_env == "make_new" and (normalize_obs or normalize_rew):
        env = VecNormalize(env, norm_obs=normalize_obs,norm_reward=normalize_rew,norm_obs_keys=norm_obs_keys)
    # Load normalized env
    elif normalize_env == "load_file" and (normalize_obs or normalize_rew):
        env = VecNormalize.load(load_vecnormalize_path, env)
    else: 
        exit("Write either make_new or load_file")

    
    # Load model
    if policy == 'PPO':
            model = PPO.load(load_model_path, env=env)
    elif policy == 'SAC':
        model = SAC.load(load_model_path, env=env)
        
    env.training = False

    record_video(
        env=env, 
        model=model,
        video_length = horizon, 
        num_episodes= num_episodes, 
        name_of_video_file=name_of_video_file,
        fps = control_freq)
    env.close()
