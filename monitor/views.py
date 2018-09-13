from django.shortcuts import render
from django.http import StreamingHttpResponse, HttpResponse
from django.http.response import HttpResponseServerError
from django.views.decorators import gzip
#from monitor.ssd_tensorflow.notebooks.ssd_tensorflow import detect_image
from tiny_yolo import tiny_yolo_gen
from user.views import check_cookie
from multiprocessing import Process, Queue

import time
import json
import cv2
import tensorflow
import os

detection_process = False
detection_process_username = None
QList = {}

#from queue import Queue
'''
class DetectionThread(Thread):
    def __init__(self, frame, q):
        super().__init__()
        self.finished = False
        self.frame = frame
        self.q = q

    def run(self):
        try:
            frame = detect_image(self.frame)
            self.q.put(frame)
        except:
            print('runerror')
'''


        #ret, jpeg = cv2.imencode('.jpg', image)
        #return jpeg.tobytes()
'''
def gen(camera):
    q = Queue()
    with open('config.json', 'r') as f:
        conf = json.load(f)
    height = int(conf['height'])
    while True:
        frame = camera.get_frame()
        frame = cv2.resize(frame, (height, int(height*frame.shape[0]/frame.shape[1])))
        thr = DetectionThread(frame, q)
        thr.start()
        start_time = time.time()
        while True:
            t_frame = camera.get_frame()
            if not q.empty():
                break
        frame = q.get()
        end_time = time.time()
        print(end_time - start_time)

        ret, jpeg = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
    print('succeed')
'''

def gen():
    q = Queue()
    p = Process(target=tiny_yolo_gen, args=(q, ))
    p.start()
    current_connected = True
    while True:
        if not q.empty():
            res = q.get()
            for i in QList:
                QList[i].put(res)
            if current_connected:
                try:
                    yield res
                except:
                    current_connected = False
                    global detection_process_username
                    detection_process_username = None
            else:
                if len(QList) == 0:
                    p.terminate()
                    global detection_process
                    detection_process = False
                    break


def fetch(username):
    q = Queue()
    QList[username] = q
    while True:
        if not q.empty():
            try:
                yield q.get()
            except:
                del QList[username]
                break

@gzip.gzip_page
def video_feed(request):
    status = check_cookie(request)
    if status[0] == -1:
        return render(request, 'redirect.html', {'message': '请登录后查看', 'url': '/login'})
    username = status[1]
    global detection_process_username, QList
    if username in QList or username == detection_process_username:
        return render(request, 'redirect.html', {'message': '对不起，当前用户正在登录查看中，请使用其他账号登录查看或下线', 'url': '/'})
    global detection_process
    if not detection_process:
        detection_process = True
        detection_process_username = username
        try:
            return StreamingHttpResponse(gen(),content_type="multipart/x-mixed-replace;boundary=frame")
        except:
            print("aborted")
    else:
        try:
            return StreamingHttpResponse(fetch(username),content_type="multipart/x-mixed-replace;boundary=frame")
        except:
            print('aborted')

def monitor(request):
    status = check_cookie(request)
    if status[0] == -1:
        return render(request, 'redirect.html', {'message': '请登录后查看', 'url': '/login'})
    username = status[1]
    if username in QList or username == detection_process_username:
        return render(request, 'redirect.html', {'message': '对不起，当前用户正在登录查看中，请使用其他账号登录查看或下线', 'url': '/'})
    return render(request, 'monitor.html')
