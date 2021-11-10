import csv
import os
import sys
import cv2

import numpy as np
from stable_baselines3 import PPO, A2C
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.atari_wrappers import MaxAndSkipEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import VecFrameStack, DummyVecEnv

from map_enemy_id_to_name import id_to_name

algorithm = sys.argv[1]
runs = int(sys.argv[2])
if runs < 0:
    runs = sys.maxsize
if algorithm != 'PPO' and algorithm != 'A2C':
    print("Please use PPO or A2C for the algorithm")
    sys.exit()

sys.path.insert(0, 'evoman')
from gym_environment import Evoman

environments = [
    [(
        VecFrameStack(DummyVecEnv(
            [lambda: MaxAndSkipEnv(Monitor(Evoman(
                enemyn=str(n),
                weight_player_hitpoint=weight_player_hitpoint,
                weight_enemy_hitpoint=1.0 - weight_player_hitpoint,
                randomini=True,
            )), skip=2)]
        ), n_stack=3),
        VecFrameStack(DummyVecEnv(
            [lambda: MaxAndSkipEnv(Monitor(Evoman(
                enemyn=str(n),
                weight_player_hitpoint=1,
                weight_enemy_hitpoint=1,
                randomini=True,
            )), skip=2)]
        ), n_stack=3)
    ) for weight_player_hitpoint in [0.1, 0.4, 0.5]]
    for n in range(2, 9)
]


class EvalEnvCallback(BaseCallback):
    def __init__(
            self,
            eval_env,
            l_writer,
            r_writer,
            models_dir = None,
            video_dir = None,
            raw_data_dir = None,
            verbose: int = 0,
            lengths_prepend: list = [],
            rewards_prepend: list = [],
            n_eval_episodes: int = 5,
            eval_freq: int =  10000,
            model_freq: int = 100000,
            video_freq: int = 250000,
    ):
        super(EvalEnvCallback, self).__init__(verbose=verbose)
        if not os.path.exists(models_dir) and models_dir is not None:
            os.makedirs(models_dir)
        if not os.path.exists(video_dir) and video_dir is not None:
            os.makedirs(video_dir)
        if not os.path.exists(raw_data_dir) and raw_data_dir is not None:
            os.makedirs(raw_data_dir)
        self.eval_env = eval_env
        self.l_writer = l_writer
        self.r_writer = r_writer
        self.lengths_prepend = lengths_prepend
        self.rewards_prepend = rewards_prepend
        self.video_dir = video_dir
        self.model_freq = model_freq
        self.video_freq = video_freq
        self.n_eval_episodes = n_eval_episodes
        self.eval_freq = eval_freq
        self.lengths = []
        self.rewards = []
        self.models_dir = models_dir
        self.raw_data_dir = raw_data_dir

    def _on_step(self) -> bool:
        if self.n_calls % self.model_freq == 0:
            if self.models_dir is not None:
                self.model.save(f'{self.models_dir}/{self.n_calls}.model')

        if self.n_calls % self.video_freq == 0:
            if self.video_dir is not None:
                self.eval_env.envs[0].env.env.keep_frames = True
                obs = self.eval_env.reset()

                fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
                fps = 30
                video_filename = f'{self.video_dir}/{self.n_calls}.avi'
                out = cv2.VideoWriter(video_filename, fourcc, fps, (self.eval_env.envs[0].WIDTH, self.eval_env.envs[0].HEIGHT))
                for _ in range(3500):
                    action, _state = model.predict(obs, deterministic=False)
                    obs, reward, done, info = self.eval_env.step(action)
                    if done:
                        break
                for frame in self.eval_env.render("p_video"):
                    out.write(frame)
                out.release()
                self.eval_env.envs[0].env.env.keep_frames = False

        if self.n_calls % self.eval_freq == 0:
            with open(f'{self.raw_data_dir}/wins.csv', mode='a') as wins_file:
                wins_writer = csv.writer(wins_file, delimiter=',', quotechar='\'', quoting=csv.QUOTE_NONNUMERIC)
                with open(f'{self.raw_data_dir}/rewards.csv', mode='a') as rewards_file:
                    rewards_writer = csv.writer(rewards_file, delimiter=',', quotechar='\'', quoting=csv.QUOTE_NONNUMERIC)
                    wins = []
                    rs = []
                    ls = []
                    for j in range(self.n_eval_episodes):
                        obs = self.eval_env.reset()
                        rew = 0

                        for s in range(3500):
                            action, _state = self.model.predict(obs, deterministic=False)
                            obs, [reward], done, info = self.eval_env.step(action)
                            rew = rew + reward
                            if done:
                                print(rew, self.eval_env.envs[0].env.env.enemy.life, self.eval_env.envs[0].env.env.player.life)
                                if self.eval_env.envs[0].env.env.enemy.life <= 0:
                                    wins.append(1)
                                else:
                                    wins.append(0)
                                ls.append(s)
                                break
                        rs.append(rew)
                    self.lengths.append(np.mean(ls))
                    self.rewards.append(np.mean(rs))
                    wins_writer.writerow([self.n_calls, self.n_eval_episodes, ''] + wins)
                    rewards_writer.writerow([self.n_calls, self.n_eval_episodes, ''] + rs)

        return True

    def _on_training_end(self) -> None:
        self.l_writer.writerow(self.lengths_prepend+self.lengths)
        self.r_writer.writerow(self.rewards_prepend+self.rewards)


for run in range(runs):
    print(f'Starting run {run}!')
    baseDir = f'FullTime/{algorithm}/run{run}'

    if not os.path.exists(baseDir):
        os.makedirs(baseDir)

    for enemy_id, enemy_envs in enumerate(environments, start=1):
        enemyDir = f'{baseDir}/{id_to_name(enemy_id)}'
        if not os.path.exists(enemyDir):
            os.makedirs(enemyDir)
        with open(f'{enemyDir}/Evaluation_lengths.csv', mode='a') as eval_lengths_file:
            eval_lengths_writer = csv.writer(eval_lengths_file, delimiter=',', quotechar='\'', quoting=csv.QUOTE_NONNUMERIC)
            with open(f'{enemyDir}/Evaluation_rewards.csv', mode='a') as eval_rewards_file:
                eval_rewards_writer = csv.writer(eval_rewards_file, delimiter=',', quotechar='\'', quoting=csv.QUOTE_NONNUMERIC)
                with open(f'{enemyDir}/Training_lengths.csv', mode='a') as train_lengths_file:
                    train_lengths_writer = csv.writer(train_lengths_file, delimiter=',', quotechar='\'', quoting=csv.QUOTE_NONNUMERIC)
                    with open(f'{enemyDir}/Training_rewards.csv', mode='a') as train_rewards_file:
                        train_rewards_writer = csv.writer(train_rewards_file, delimiter=',', quotechar='\'', quoting=csv.QUOTE_NONNUMERIC)

                        for env, eval_env in enemy_envs:
                            modelDir = f'{enemyDir}/models/{({env.envs[0].env.env.weight_player_hitpoint}, {env.envs[0].env.env.weight_enemy_hitpoint})}'
                            videoDir = f'{enemyDir}/videos/{({env.envs[0].env.env.weight_player_hitpoint}, {env.envs[0].env.env.weight_enemy_hitpoint})}'
                            rawDataDir = f'{enemyDir}/raw-data/{({env.envs[0].env.env.weight_player_hitpoint}, {env.envs[0].env.env.weight_enemy_hitpoint})}'
                            if not os.path.exists(modelDir):
                                os.makedirs(modelDir)
                            if not os.path.exists(videoDir):
                                os.makedirs(videoDir)
                            if not os.path.exists(rawDataDir):
                                os.makedirs(rawDataDir)
                            env.envs[0].env.env.keep_frames = False
                            if algorithm == 'A2C':
                                model = A2C('MlpPolicy', env)
                            else:
                                model = PPO('MlpPolicy', env)
                            l_prepend = [f'{id_to_name(enemy_id)}', ""]
                            r_prepend = [f'{id_to_name(enemy_id)} ({env.envs[0].env.env.weight_player_hitpoint}, {env.envs[0].env.env.weight_enemy_hitpoint})', str(env.envs[0].env.env.win_value())]
                            model.learn(total_timesteps=int(2.5e5), callback=EvalEnvCallback(
                                eval_env=eval_env,
                                l_writer=eval_lengths_writer,
                                r_writer=eval_rewards_writer,
                                models_dir=modelDir,
                                video_dir=videoDir,
                                raw_data_dir=rawDataDir,
                                lengths_prepend=l_prepend,
                                rewards_prepend=r_prepend,
                                eval_freq=12500,
                                n_eval_episodes=25,
                            ))

                            train_lengths_writer.writerow(l_prepend+env.envs[0].get_episode_lengths())
                            train_rewards_writer.writerow(r_prepend+env.envs[0].get_episode_rewards())

                            print(f'\nFinished {id_to_name(enemy_id)} ({env.envs[0].env.env.weight_player_hitpoint}, {env.envs[0].env.env.weight_enemy_hitpoint})')

        print(f'\n\nFinished {id_to_name(enemy_id)} completely\n\n')
                # env.envs[0].env.env.keep_frames = True
                # for j in range(10):
                #     obs = env.reset()
                #
                #     fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
                #     fps = 30
                #     video_filename = f'Optimized_FStack_FSkip/PPO_env{i}_run{j}.avi'
                #     out = cv2.VideoWriter(video_filename, fourcc, fps, (env.envs[0].WIDTH, env.envs[0].HEIGHT))
                #     for _ in range(2500):
                #         action, _state = model.predict(obs, deterministic=False)
                #         obs, reward, done, info = env.step(action)
                #         if done:
                #             break
                #     for frame in env.render("p_video"):
                #         out.write(frame)
                #     out.release()


# for env in environments:
#     i += 1
#
#     model.set_env(env)
#     model.learn(total_timesteps=(2 ** 17))
#
#     print(f'\n\n\nFinished learning env{i}!\n\n\n')
#
#     obs = env.reset()
#
#     fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
#     fps = 30
#     video_filename = f'env{i}_({fsn}, 10,2).avi'
#     out = cv2.VideoWriter(video_filename, fourcc, fps, (env.WIDTH, env.HEIGHT))
#     for _ in range(2500):
#         action, _state = model.predict(obs, deterministic=False)
#         obs, reward, done, info = env.step(action)
#         out.write(env.render("bgr"))
#         if done:
#             break
#     out.release()