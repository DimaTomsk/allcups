import psutil

for process in psutil.process_iter():
    process.kill()
    
