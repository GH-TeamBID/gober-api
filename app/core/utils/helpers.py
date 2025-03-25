import os

class Envs:
    @staticmethod
    def get(name):
        env_value = os.getenv(name)
        if env_value == 'True': env_value = True
        elif env_value == 'False': env_value = False
        return env_value