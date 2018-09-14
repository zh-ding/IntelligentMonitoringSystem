from django.shortcuts import render
from django.http import StreamingHttpResponse, HttpResponse
from django.http.response import HttpResponseServerError
from django.views.decorators import gzip
from tiny_yolo import tiny_yolo_gen
from user.views import check_cookie
from multiprocessing import Process, Queue

import time
import json
import cv2
import tensorflow
import os
import json

detection_process = False
detection_process_username = None
QList = {}
QNameList = {}

def gen():
    q = Queue()
    q_name = Queue()
    p = Process(target=tiny_yolo_gen, args=(q, q_name))
    p.start()
    current_connected = True
    global detection_process, QNameList
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
                    if len(QList) == 0:
                        p.terminate()
                        detection_process = False
                        break
            else:
                if len(QList) == 0:
                    p.terminate()
                    detection_process = False
                    break
        while not q_name.empty():
            name = q_name.get()
            if name == 'Unknown':
                continue
            for i in  QNameList:
                QNameList[i].append(name)


def fetch(username):
    q = Queue()
    QList[username] = q
    while True:
        if not q.empty():
            try:
                yield q.get()
            except:
                del QList[username]
                del QNameList[username]
                break

def get_black_name(request):
    status = check_cookie(request)
    if status[0] == -1:
        return render(request, 'redirect.html', {'message': 'Unauthorized.', 'url': '/login'})
    username = status[1]
    global QNameList
    namelist = list(set(QNameList[username]))
    QNameList[username] = []
    resp = {'name': namelist}
    return HttpResponse(json.dumps(resp), content_type="application/json")

@gzip.gzip_page
def video_feed(request):
    status = check_cookie(request)
    if status[0] == -1:
        return render(request, 'redirect.html', {'message': 'Unauthorized.', 'url': '/login'})
    username = status[1]
    global detection_process_username, QList
    if username in QList or username == detection_process_username:
        return render(request, 'redirect.html', {'message': 'Current user is right now watching, please use another account.', 'url': '/'})
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
        return render(request, 'redirect.html', {'message': 'Unauthorized.', 'url': '/login'})
    username = status[1]
    QNameList[username] = []
    if username in QList or username == detection_process_username:
        return render(request, 'redirect.html', {'message': 'Current user is right now watching, please use another account.', 'url': '/'})
    return render(request, 'monitor.html', {'username': username})
