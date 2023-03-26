import json
import sys

lines = sys.stdin.readlines()

joined_lines = ''.join(lines)[:100000]

print(json.dumps(joined_lines))
