import json
import os
import resource
import subprocess
import sys
import time
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Awaitable
from typing import Union

import psutil
from tornado.concurrent import Future
from tornado.gen import sleep
from tornado import gen
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient

from .helpers import loads, log, log_error, truncate
from .tests_getter import TestsGetter


@dataclass(repr=False, eq=False)
class SolutionTester:
    task_container_ip: str
    task_container_port: int
    solution_id: str
    run_command: str

    # How many times we try to connect to the task server
    connection_tries_number: int
    # Number of seconds to wait between tries
    connection_tries_delay_s: int

    end_symbol = b'\n'

    executor = ThreadPoolExecutor()

    @staticmethod
    def resource_monitor(pid, max_ram_usage_bytes, max_cpu_secs):
        peak_ram_usage_bytes = 0
        peak_cpu_secs = 0
        exit_code = None

        try:
            process = psutil.Process(pid)
        except (psutil.ZombieProcess, psutil.AccessDenied, psutil.NoSuchProcess):
            return exit_code, peak_ram_usage_bytes, peak_cpu_secs

        while True:
            try:
                ram_usage_bytes = process.memory_info().rss
                cpu_secs = process.cpu_times().user

                peak_ram_usage_bytes = max(ram_usage_bytes, peak_ram_usage_bytes)
                peak_cpu_secs = max(cpu_secs, peak_cpu_secs)

                if max_ram_usage_bytes and ram_usage_bytes > max_ram_usage_bytes:
                    process.kill()
                    exit_code = 'ML'
                    break

                if cpu_secs > max_cpu_secs:
                    process.kill()
                    exit_code = 'CTL'
                    break
            except (psutil.ZombieProcess, psutil.AccessDenied, psutil.NoSuchProcess):
                break

        return exit_code, peak_ram_usage_bytes, peak_cpu_secs

    def __post_init__(self):
        self.stream = None
        self.tests = TestsGetter.load_tests()
        self.num_symbols_to_truncate = os.environ.get('NUM_TO_TRUNCATE', 300)

    def read(self) -> Awaitable[bytes]:
        return self.stream.read_until(self.end_symbol)

    def write(self, message: Union[str, dict]) -> "Future[None]":
        if isinstance(message, dict):
            sent_message = {
                key: truncate(str(value)) if key != 'error' else value
                for key, value in message.items()
            }
            # log(f'Sent: {json.dumps(sent_message, indent=4)}')
            message = json.dumps(message)
        else:
            # log(f'Sent: {message}')
            pass

        return self.stream.write(self.encode_message(message))

    def encode_message(self, message: str) -> bytes:
        if not isinstance(message, str):
            message = str(message)

        return f'{message}'.encode() + self.end_symbol

    @staticmethod
    def get_constraints(constraints) -> tuple:
        ram_limit = constraints.get('peak_ram_used_mb', 256) * 1024 * 1024  # Converting to bytes
        swap_limit = constraints.get('peak_swap_used_mb', 0) * 1024 * 1024  # Converting to bytes
        cpu_limit = constraints.get('cpu_execution_time_s', 100)
        time_limit = constraints.get('execution_time_s', 100)
        return ram_limit, swap_limit, cpu_limit, time_limit

    @staticmethod
    def check_constraints(test_data: dict) -> None:
        assert 'constraints' in test_data, 'Test sources does not contain constraints'

        constraints = test_data['constraints']

        # Checking constraints
        should_raise = False
        constraint_keys = ('peak_ram_used_mb', 'peak_swap_used_mb',
                           'cpu_execution_time_s', 'execution_time_s')
        for key in constraint_keys:
            constraint = constraints.get(key)
            if constraint and not isinstance(constraint, int):
                log_error(f'"{key}" value must be of type int, not {type(constraint)}.')
                should_raise = True

        if should_raise:
            raise ValueError('Constraint sources contains wrong type of values.')

    def connect(self):
        return TCPClient().connect(self.task_container_ip, self.task_container_port)

    @gen.coroutine
    def test_solution(self):
        # Connecting to the task server.
        log(f'Trying to connect to the task container on: '
            f'{self.task_container_ip}:{self.task_container_port}')

        for i in range(1, self.connection_tries_number + 1):
            try:
                self.stream = yield self.connect()
            except StreamClosedError:
                if i < self.connection_tries_number:
                    log_error(
                        f'{i}/{self.connection_tries_number}. '
                        f'Connection failed. Waiting {self.connection_tries_delay_s}s.')
                    yield sleep(self.connection_tries_delay_s)
                else:
                    log_error(f'{self.connection_tries_number} attempts failed. Exiting.')
                    return
            else:
                log('Connected.')
                break

        try:
            yield self.write(self.solution_id)

            ran_tests = 0
            for i in range(len(self.tests)):
                # Test sources is a list of strings
                test = yield self.read()
                test_data = loads(test)
                if not test_data:
                    return

                test_result = self.run_test(test_data=test_data)
                yield self.write(test_result)
                ran_tests += 1

                if test_result['returncode'] != 0:
                    log_error(f'Returncode is {test_result["returncode"]}')
                    break

            log(f'Ran {ran_tests} tests. Finishing.')
            return

        except Exception as error:
            log_error(f'Got unexpected error: {error}.')
            raise

    def run_test(self, test_data: dict) -> dict:
        self.check_constraints(test_data)
        ram_limit, swap_limit, cpu_limit, time_limit = (
            self.get_constraints(test_data['constraints']))

        test_name = test_data['test_name']
        log(f'Running test "{test_name}"')

        if test_name not in self.tests:
            log_error(f'No test with name "{test_name}"')
            sys.exit(1)

        # Input lines for the solution
        test_lines = self.tests[test_name]
        log(test_lines)
        process = subprocess.Popen(
            self.run_command.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        future = self.executor.submit(self.resource_monitor, process.pidid, ram_limit, cpu_limit)

        started_testing = time.time()

        return_code = None
        try:
            output, error = process.communicate(input='\n'.join(test_lines).encode(), timeout=time_limit)
            log(output, error)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            output, error = 'TL'.encode(), f'Timeout ({time_limit}s)'.encode()
            return_code = 124
        finally:
            info = resource.getrusage(resource.RUSAGE_CHILDREN)
            execution_time_s = time.time() - started_testing

            exit_code, peak_ram_usage_bytes, peak_cpu_secs = future.result()

            if exit_code == 'ML':
                return_code = 7
            elif exit_code == 'CTL':
                return_code = -9

        conversion_error = None
        try:
            output = output.decode().strip()
        except UnicodeDecodeError as e:
            conversion_error = str(e)
            output = ''

        try:
            error = error.decode()
        except UnicodeDecodeError:
            error = str(error)

        return {
            'test_name': test_name,
            'output': output,
            'error': error,
            'output_conversion_error': conversion_error,
            'returncode': return_code if return_code else process.returncode,
            'peak_ram_used_mb': peak_ram_usage_bytes / (1024.0 * 1024.0),
            'peak_swap_used_mb': info.ru_nswap / 1024.0,
            'cpu_execution_time_s': peak_cpu_secs,
            'execution_time_s': execution_time_s,
        }
