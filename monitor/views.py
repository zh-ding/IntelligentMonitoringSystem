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

detection_process = False
detection_process_username = None
QList = {}

def gen():
    q = Queue()
    p = Process(target=tiny_yolo_gen, args=(q, ))
    p.start()
    current_connected = True
    global detection_process
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
