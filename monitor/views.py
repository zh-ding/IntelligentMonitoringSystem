from django.shortcuts import render
from django.http import StreamingHttpResponse, HttpResponse
from django.http.response import HttpResponseServerError
from django.views.decorators import gzip
from tiny_yolo import tiny_yolo_gen
from user.views import check_cookie
import multiprocessing
import queue
import threading

import time
import json
import cv2
import tensorflow
import os
import json

detection_process = False
detection_process_username = None
QRespList = {}
QNameList = {}
q_resp = multiprocessing.Queue()
q_name = multiprocessing.Queue()

class ReadFromAnotherProcess(threading.Thread):    
    def __init__(self, QRespList, QNameList):
        super().__init__()
        self.QRespList = QRespList
        self.QNameList = QNameList

    def run(self):
        while True:
            if not q_resp.empty():
                res = q_resp.get()
                for i in self.QRespList:
                    self.QRespList[i].put(res)
            while not q_name.empty():
                name = q_name.get()
                if name == 'Unknown':
                    continue
                for i in self.QNameList:
                    self.QNameList[i].append(name)
            time.sleep(0.02)

p = multiprocessing.Process(target=tiny_yolo_gen, args=(q_resp, q_name))
p.start()
th_rfap = ReadFromAnotherProcess(QRespList, QNameList)
th_rfap.start()

def fetch(username):
    while True:
        if not QRespList[username].empty():
            res = QRespList[username].get()
            try:
                yield res
            except:
                del QRespList[username]
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
    if username in QRespList:
        return render(request, 'redirect.html', {'message': 'Current user is right now watching, please use another account.', 'url': '/'})
    QNameList[username] = []
    QRespList[username] = queue.Queue()
    try:
        return StreamingHttpResponse(fetch(username),content_type="multipart/x-mixed-replace;boundary=frame")
    except:
        print('aborted')

def monitor(request):
    status = check_cookie(request)
    if status[0] == -1:
        return render(request, 'redirect.html', {'message': 'Unauthorized.', 'url': '/login'})
    username = status[1]
    if username in QRespList:
        return render(request, 'redirect.html', {'message': 'Current user is right now watching, please use another account.', 'url': '/'})
    return render(request, 'monitor.html', {'username': username})
