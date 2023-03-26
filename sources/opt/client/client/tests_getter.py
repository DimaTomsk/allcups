import json
import os


class TestsGetter:

    data_folder = '/tmp/sources'

    @classmethod
    def load_data(cls) -> tuple:
        answers: dict = cls._get_folder_contents('answers')
        constraints: dict = cls._get_folder_contents('constraints', is_json=True)
        for key in list(constraints.keys()):
            constraints[key.replace('.json', '')] = constraints.pop(key)
        return answers, constraints

    @classmethod
    def load_tests(cls) -> dict:
        return cls._get_folder_contents('tests')

    @classmethod
    def _get_folder_contents(cls, folder_name: str, is_json: bool = False) -> dict:
        result = {}
        folder = os.path.join(cls.data_folder, folder_name)
        file_names = sorted([
            file_name for file_name in os.listdir(folder)
            if not file_name.startswith('.')])

        for file_name in file_names:
            file_path = os.path.join(folder, file_name)

            with open(file_path, 'r') as f:
                if is_json:
                    result[file_name] = json.load(f)
                else:
                    result[file_name] = f.read().splitlines()

        return result
