import multiprocessing

bind = "127.0.0.1:__PORT__"
workers = multiprocessing.cpu_count() * 2 + 1

capture_output = True
loglevel = "info"
accesslog = "__LOG_FILE__"
errorlog = "__LOG_FILE__"

pidfile = "__DATA_DIR__/gunicorn.pid"
