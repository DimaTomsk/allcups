import json

from tornado.ioloop import IOLoop

from client.client import SolutionTester
from client.helpers import get_solution_tester_init_params


if __name__ == '__main__':
    init_params = get_solution_tester_init_params()
    print(f'Container init params:\n{json.dumps(init_params, indent=4)}')

    IOLoop.current().run_sync(SolutionTester(
        **init_params
    ).test_solution)
