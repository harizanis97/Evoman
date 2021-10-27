import cv2
import sys
from stable_baselines3 import PPO
from stable_baselines3.common.atari_wrappers import MaxAndSkipEnv

sys.path.insert(0, 'evoman')
from gym_environment import Evoman

fsn = 2

environments = [MaxAndSkipEnv(Evoman(enemyn=str(1)), skip=2)]

model = PPO('MlpPolicy', environments[0], verbose=1)

i = 0

for env in environments:
    i += 1

    model.set_env(env)
    model.learn(total_timesteps=(2 ** 16))

    print(f'\n\n\nFinished learning env{i}!\n\n\n')

    env.env.keep_frames = True
    obs = env.reset()

    fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
    fps = 30
    video_filename = f'env{i}_({fsn}, 10,2).avi'
    out = cv2.VideoWriter(video_filename, fourcc, fps, (env.WIDTH, env.HEIGHT))
    for _ in range(2500):
        action, _state = model.predict(obs, deterministic=False)
        obs, reward, done, info = env.step(action)
        if done:
            for frame in env.render('video'):
                out.write(frame)
            break
    out.release()