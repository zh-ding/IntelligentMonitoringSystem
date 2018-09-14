import face_recognition
import os
import cv2
from threading import Thread
import json
from django.core.mail import send_mail
import time

facelist = os.listdir('facedata/')
known_face_encodings = []
known_face_names = []

for file in facelist:
    face_image = face_recognition.load_image_file("facedata/" + file)
    print(file)
    face_encoding = face_recognition.face_encodings(face_image)[0]
    known_face_encodings.append(face_encoding)
    known_face_names.append(file.split('.')[0])


class MailThread(Thread):
    def __init__(self, name, datetime):
        super().__init__()
        self.name = name
        self.datetime = datetime

    def run(self):
        with open('config.json') as f:
            mail = json.load(f)['mail']
        send_mail('[alert!]' + self.datetime + ' ' + self.name + ' appeared!!!', 
            'This is an automated email. Be aware of this alert!', 
            mail['EMAIL_HOST_USER'], 
            mail['RECIPIENT_LIST'],
        )

def face_rec(frame, q):
    
    # Resize frame of video to 1/4 size for faster face recognition processing
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

    # Convert the image from BGR color (which OpenCV uses) to RGB color (which face_recognition uses)
    rgb_small_frame = small_frame[:, :, ::-1]

    # Only process every other frame of video to save time
        # Find all the faces and face encodings in the current frame of video
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    face_names = []
    for face_encoding in face_encodings:
        # See if the face is a match for the known face(s)
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"

        # If a match was found in known_face_encodings, just use the first one.
        if True in matches:
            first_match_index = matches.index(True)
            name = known_face_names[first_match_index]

        face_names.append(name)
        if name != 'Unknown':
            th_mail = MailThread(name, time.strftime("%a, %d %b %Y %H:%M:%S"))
            th_mail.start()


    # Display the results
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        # Scale back up face locations since the frame we detected in was scaled to 1/4 size
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4

        dic = {}
        dic['left'] = left
        dic['bottom'] = bottom
        dic['right'] = right
        dic['name'] = name
        q.put(dic)

        

