import os
import time
import cv2
import numpy as np
import tensorflow as tf
from keras import backend as K
from keras.models import load_model
from yad2k.models.keras_yolo import yolo_head, yolo_boxes_to_corners
from utils.yolo_utils import read_classes, read_anchors, generate_colors, preprocess_image, draw_boxes, scale_boxes
from multiprocessing import Queue
import json
from threading import Thread
import queue
import threading
from face import face_rec

scores = None
boxes = None
classes = None

image_shape = None
yolo_outputs = None

yolo_model = None
class_names = None
anchors = None

sess = None


def yolo_eval(yolo_outputs, image_shape=(720., 1280.), max_boxes=10, score_threshold=.6, iou_threshold=.5):    
    # Retrieve outputs of the YOLO model (≈1 line)
    box_confidence, box_xy, box_wh, box_class_probs = yolo_outputs

    # Convert boxes to be ready for filtering functions 
    boxes = yolo_boxes_to_corners(box_xy, box_wh)

    # Use one of the functions you've implemented to perform Score-filtering with a threshold of score_threshold (≈1 line)
    scores, boxes, classes = yolo_filter_boxes(box_confidence, boxes, box_class_probs, score_threshold)
    
    # Scale boxes back to original image shape.
    boxes = scale_boxes(boxes, image_shape) # boxes: [y1, x1, y2, x2]

    # Use one of the functions you've implemented to perform Non-max suppression with a threshold of iou_threshold (≈1 line)
    scores, boxes, classes = yolo_non_max_suppression(scores, boxes, classes, max_boxes, iou_threshold)
    
    ### END CODE HERE ###
    
    return scores, boxes, classes

def yolo_filter_boxes(box_confidence, boxes, box_class_probs, threshold = .6):    
    # Compute box scores
    box_scores = box_confidence * box_class_probs
    
    # Find the box_classes thanks to the max box_scores, keep track of the corresponding score
    box_classes = K.argmax(box_scores, axis=-1)
    box_class_scores = K.max(box_scores, axis=-1, keepdims=False)
    
    # Create a filtering mask based on "box_class_scores" by using "threshold". The mask should have the
    # same dimension as box_class_scores, and be True for the boxes you want to keep (with probability >= threshold)
    filtering_mask = box_class_scores >= threshold
    
    # Apply the mask to scores, boxes and classes
    scores = tf.boolean_mask(box_class_scores, filtering_mask)
    boxes = tf.boolean_mask(boxes, filtering_mask)
    classes = tf.boolean_mask(box_classes, filtering_mask)
    
    return scores, boxes, classes


def yolo_non_max_suppression(scores, boxes, classes, max_boxes = 10, iou_threshold = 0.5):
    max_boxes_tensor = K.variable(max_boxes, dtype='int32') # tensor to be used in tf.image.non_max_suppression()
    K.get_session().run(tf.variables_initializer([max_boxes_tensor])) # initialize variable max_boxes_tensor
    
    # Use tf.image.non_max_suppression() to get the list of indices corresponding to boxes you keep
    nms_indices = tf.image.non_max_suppression(boxes, scores, max_boxes, iou_threshold)
    
    # Use K.gather() to select only nms_indices from scores, boxes and classes
    scores = K.gather(scores, nms_indices)
    boxes = K.gather(boxes, nms_indices)
    classes = K.gather(classes, nms_indices)
    
    return scores, boxes, classes

def image_detection(sess, image_path, image_file):
    # Preprocess your image
    image, image_data = preprocess_image(image_path + image_file, model_image_size = (416, 416))
    
    # Run the session with the correct tensors and choose the correct placeholders in the feed_dict.
    # You'll need to use feed_dict={yolo_model.input: ... , K.learning_phase(): 0})
    out_scores, out_boxes, out_classes = sess.run([scores, boxes, classes], feed_dict={yolo_model.input:image_data, K.learning_phase():0})

    # Print predictions info
    print('Found {} boxes for {}'.format(len(out_boxes), image_file))
    # Generate colors for drawing bounding boxes.
    colors = generate_colors(class_names)
    # Draw bounding boxes on the image file
    image = draw_boxes(image, out_scores, out_boxes, out_classes, class_names, colors)
    # Save the predicted bounding box on the image
    #image.save(os.path.join("out", image_file), quality=90)
    cv2.imwrite(os.path.join("out", image_file), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    
    return out_scores, out_boxes, out_classes

def video_detection(sess, image):
    resized_image = cv2.resize(image, (416, 416), interpolation=cv2.INTER_AREA)
    resized_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
    image_data = np.array(resized_image, dtype='float32')
    image_data /= 255.
    image_data = np.expand_dims(image_data, 0)

    out_scores, out_boxes, out_classes = sess.run([scores, boxes, classes], feed_dict={yolo_model.input:image_data, K.learning_phase():0})

    colors = generate_colors(class_names)

    image = draw_boxes(image, out_scores, out_boxes, out_classes, class_names, colors)

    return image


class VideoCamera(object):
    lock = threading.Lock()
    def __init__(self):
        with open('config.json', 'r') as f:
            conf = json.load(f)
        self.video = cv2.VideoCapture(conf['rtspURL'])
    
    def __del__(self):
        self.video.release()
    
    def get_frame(self):
        with VideoCamera.lock:
            return self.video.read()

class FilterThread(Thread):
    def __init__(self, camera, q):
        Thread.__init__(self) 
        self.camera = camera
        self.q = q

    def run(self):
        while True:
            self.camera.get_frame()
            if not self.q.empty():
                self.q.get()
                break

class FaceThread(Thread):
    def __init__(self, frame, q):
        super().__init__()
        self.frame = frame
        self.q = q

    def run(self):
        face_rec(self.frame, self.q)


def tiny_yolo_gen(q_resp, q_name):
    camera = VideoCamera()
    global sess
    global yolo_model, class_names, anchors
    global image_shape, yolo_outputs
    global scores, boxes, classes
    ret, frame = camera.get_frame()
    with open('config.json', 'r') as f:
        conf = json.load(f)
    height = int(conf['height'])
    frame = cv2.resize(frame, (height, int(height*frame.shape[0]/frame.shape[1])))
    if not sess:
        sess = K.get_session()
    yolo_model = load_model("monitor/tiny_yolo_keras/model_data/tiny-yolo.h5")    
    class_names = read_classes("monitor/tiny_yolo_keras/model_data/yolo_coco_classes.txt")
    anchors = read_anchors("monitor/tiny_yolo_keras/model_data/yolo_anchors.txt")
    image_shape = np.float32(frame.shape[0]), np.float32(frame.shape[1])
    yolo_outputs = yolo_head(yolo_model.output, anchors, len(class_names))
    scores, boxes, classes = yolo_eval(yolo_outputs, image_shape=image_shape, score_threshold=.3)
    
    
    face_q = queue.Queue()
    que = queue.Queue()
    while ret:
        th = FilterThread(camera, que)
        th.start()
        face_th = FaceThread(frame, face_q)
        face_th.start()
        start = time.time()
        image = video_detection(sess, frame)
        end = time.time()
        t = end - start
        fps  = "Fps1: {:.2f}".format(1 / t)
        #print(fps)
        face_th.join()
        que.put(1)
        end = time.time()
        t = end - start
        fps  = "Fps2: {:.2f}".format(1 / t)        
        #print(fps)
        while not face_q.empty():
            dic = face_q.get()
            cv2.rectangle(image, (dic['left'], dic['bottom'] - 35), (dic['right'], dic['bottom']), (0, 0, 255), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(image, dic['name'], (dic['left'] + 6, dic['bottom'] - 6), font, 1.0, (255, 255, 255), 1)
            q_name.put(dic['name'])

        ret, jpeg = cv2.imencode('.jpg', image)
        try:
            q_resp.put(b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            num = 0
            ret = False
            while not ret:
                ret, frame = camera.get_frame()
                num = num + 1
                if num >= 100000:
                    break
            frame = cv2.resize(frame, (height, int(height*frame.shape[0]/frame.shape[1])))
        except:
            print('yield error')
            break
    print('yolo end.')
