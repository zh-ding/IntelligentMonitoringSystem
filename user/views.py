from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
import json
import time
import pymysql
import hashlib

with open('config.json') as f:
    conf = json.load(f)

def index(request):
    status = check_cookie(request)
    if status[0] == -1:
        return HttpResponseRedirect('/login')
    elif status[0] == 0:
        return render(request, 'index_admin.html', {'userlist': getuserlist(), 'username': status[1]})
    elif status[0] == 1:
        return render(request, 'index_user.html', {'username': status[1]})


def login(request):
    if check_cookie(request)[0] != -1:
        return HttpResponseRedirect('/')
    if request.method == 'GET':
        return render(request, 'login.html', {'message': ''})
    else:
        username = request.POST['username']
        password = request.POST['password']
        userinfo = check_user(username, password)
        user_id = int(userinfo[0])
        priv = int(userinfo[1])
        if priv == 0 or priv == 1:
            timestamp = int(time.time())
            md5string = hashlib.md5((str(timestamp) + username + password).encode('utf8')).hexdigest()
            db = connect_to_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO logininfo (user_id, cookie, expiretime) VALUES (%d, '%s', %d)"%(user_id, md5string, timestamp + 7200))
            db.commit()
            db.close()
            res = render(request, 'redirect.html', {'message': 'Sign in successfully, please wait a second.', 'url': '/'})
            res.set_cookie(key='ptoken', value=md5string)
            return res
        else:
            return render(request, 'login.html', {'message': 'Wrong username or password.'})


def add_user(request):
    status = check_cookie(request)
    if status[0] != 0:
        return render(request, 'redirect.html', {'message': 'Unauthorized.', 'url': '/'})
    if request.method == 'GET':
        return render(request, 'add_user.html', {'message': '', 'username': status[1]})
    else:
        username = request.POST['username']
        password = request.POST['password']
        db = connect_to_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM user WHERE username = %s', username)
        result = cursor.fetchone()
        if result:
            return render(request, 'add_user.html', {'message': 'Username already exists, please change.', 'username': status[1]})
        cursor.execute('INSERT INTO user (username, password, priv) VALUES (%s, md5(%s), 1)', (username, password))
        db.commit()
        db.close()
        return render(request, 'redirect.html', {'message': 'Add successfully, please wait a second.', 'url': '/'})


def delete_user(request):
    status = check_cookie(request)
    if status[0] != 0:
        return render(request, 'redirect.html', {'message': 'Unauthorized.', 'url': '/'})
    user_id = request.GET['id']
    db = connect_to_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM user WHERE user_id = %s', user_id)
    db.commit()
    return render(request, 'redirect.html', {'message': 'Delete successfully, please wait a second.', 'url': '/'})


def change_password(request):
    status = check_cookie(request)
    if status[0] == -1:
        return render(request, 'redirect.html', {'message': 'Please sign in first.', 'url': '/'})
    if request.method == 'GET':
        return render(request, 'change_password.html', {'message': '', 'username': status[1]})
    else:
        current_password = request.POST['password']
        new_password = request.POST['password1']
        db = connect_to_db()
        cursor = db.cursor()
        cursor.execute('SELECT user_id FROM user WHERE username = %s and password = md5(%s)', (status[1], current_password))
        result = cursor.fetchone()
        if not result:
            return render(request, 'change_password.html', {'message': 'Incorrect password, please try again.', 'username': status[1]})
        cursor.execute("UPDATE user SET password = md5('%s') WHERE user_id = %s" % (new_password, result[0]))
        db.commit()
        return render(request, 'redirect.html', {'message': 'Change successfully, please wait a second.', 'url': '/'})


def check_cookie(request):
    if not 'ptoken' in request.COOKIES:
        return [-1]
    ptoken = request.COOKIES['ptoken']
    db = connect_to_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, expiretime FROM logininfo WHERE cookie = %s", ptoken)
    result = cursor.fetchone()
    if not result or int(time.time()) > int(result[1]):
        return [-1]
    cursor.execute("SELECT username, priv FROM user WHERE user_id = %s" % str(result[0]))
    result = cursor.fetchone()
    db.close()
    if not result:
        return [-1]
    if int(result[1]) == 0:
        return [0, result[0]]
    else:
        return [1, result[0]]


def check_user(username, password):
    db = connect_to_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, priv FROM user WHERE username = %s AND password = md5(%s)", (username, password))
    result = cursor.fetchone()
    db.close()
    if not result:
        return [-1, -1]
    return result


def getuserlist():
    db = connect_to_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, username FROM user WHERE priv = 1")
    result = cursor.fetchall()
    userlist = []
    for re in result:
        dic = {}
        dic['id'] = re[0]
        dic['name'] = re[1]
        userlist.append(dic)
    return userlist

def connect_to_db():
    db = pymysql.connect(conf['db']['ip'],
                         conf['db']['username'],
                         conf['db']['pwd'],
                         conf['db']['name'],
                         charset='utf8'
    )
    return db
