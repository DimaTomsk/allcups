import json
import os
import socket
import sys
from typing import Iterable
from typing import Optional
from typing import Union


def get_solution_tester_init_params():
    # Get from env
    params_from_env = (
        'TASK_CONTAINER_PORT', 'SOLUTION_ID', 'RUN_COMMAND',
        'CONNECTION_TRIES_NUMBER', 'CONNECTION_TRIES_DELAY_S',
    )

    # Should be set in env
    if os.environ.get('COMPILE') == 'True':
        required_env_vars = ()
    else:
        required_env_vars = ('TASK_CONTAINER_PORT', 'SOLUTION_ID', 'RUN_COMMAND', 'PROBLEM_NAME')

    default_values_for_env_vars = {
        'CONNECTION_TRIES_NUMBER': 5,
        'CONNECTION_TRIES_DELAY_S': 5,
    }

    errors = [
        f'Environment variable "{param}" is not set'
        for param in required_env_vars
        if param not in os.environ and param not in default_values_for_env_vars
    ]
    errors.extend([
        f'Environment variable "{param}" is empty'
        for param in required_env_vars
        if param in os.environ and not os.environ.get(param) and param not in default_values_for_env_vars
    ])
    assert not errors, 'Setup errors:\n{}'.format('\n'.join(errors))

    get_task_container_ip(
        task_container_id=os.environ['PROBLEM_NAME'],
        task_container_port=os.environ['TASK_CONTAINER_PORT'],
    )
    return {
        'task_container_ip': get_task_container_ip(
            task_container_id=os.environ['PROBLEM_NAME'],
            task_container_port=os.environ['TASK_CONTAINER_PORT'],
        ),
        **{
            param.lower(): os.environ.get(param, default_values_for_env_vars.get(param))
            for param in params_from_env
        }
    }


def get_task_container_ip(task_container_id: str, task_container_port: str) -> str:
    address_info = socket.getaddrinfo(task_container_id, task_container_port)
    try:
        return address_info[0][4][0]
    except (IndexError, TypeError) as e:
        log_error(f'Error trying to resolve task container ip address: {e}')
        raise


def log_error(*messages: Iterable[str]) -> None:
    """Error messages output handler."""
    print(*messages, file=sys.stderr)


def log(*messages: Iterable[str]) -> None:
    """Success messages output handler."""
    print(*messages)


def truncate(message: Union[str, bytes], up_to: int = 100) -> str:
    """Truncates a string to its first 100 symbols."""
    message_for_print = message
    if len(message_for_print) >= up_to:
        message_for_print = (
            f'{message_for_print[:up_to]}... '
            f'({len(message_for_print) - up_to} symbols truncated)')

    return message_for_print


def loads(incoming_data: bytes) -> Optional[Union[dict, list]]:
    try:
        return json.loads(incoming_data.decode())
    except ValueError as error:
        log(f'Incoming data is not valid JSON: {error}')
        log(f'Incoming data: {truncate(incoming_data)}', incoming_data)
